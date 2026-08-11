from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.expenses.enums import ExpenseType
from app.expenses.model import Expense
from app.models.category import Category
from app.models.expense_share import ExpenseShare
from app.models.spender import Spender
from app.models.trip import Trip
from app.models.trip_expense import TripExpense
from app.models.trip_expense_share import TripExpenseShare
from app.models.trip_participant import TripParticipant
from app.repositories.category_repository import CategoryRepository
from app.repositories.expense_repository import ExpenseRepository
from app.repositories.expense_share_repository import ExpenseShareRepository
from app.repositories.spender_repository import SpenderRepository
from app.services.card_transaction_share_logic import SHARE_SUM_TOLERANCE
from app.services.period_mutability import ensure_period_mutable
from app.trips.enums import PaymentMethod, TripCategory, TripStatus
from app.trips.repository import (
    TripExpenseRepository,
    TripExpenseShareRepository,
    TripParticipantRepository,
    TripRepository,
)
from app.trips.schemas import (
    PushToMonthRequest,
    TripCategoryTotal,
    TripCreate,
    TripExpenseCreate,
    TripExpenseShareInput,
    TripExpenseUpdate,
    TripParticipantInput,
    TripPersonCategoryLine,
    TripPersonConsumptionBreakdown,
    TripPersonTotal,
    TripSettlementResponse,
    TripSettlementTransfer,
    TripUpdate,
)

CENT = Decimal("0.01")
DEFAULT_TRIP_CATEGORY_NAME = "Viagem"
DEFAULT_TRIP_CATEGORY_COLOR = "#1d9bf0"


class TripService:
    """Regras de negócio para Viagens (escopo por user_id)."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._trips = TripRepository(db)
        self._participants = TripParticipantRepository(db)
        self._expenses = TripExpenseRepository(db)
        self._shares = TripExpenseShareRepository(db)
        self._spenders = SpenderRepository(db)
        self._categories = CategoryRepository(db)
        self._expense_repo = ExpenseRepository(db)
        self._expense_shares = ExpenseShareRepository(db)

    # ------------------------------------------------------------------
    # Trips CRUD
    # ------------------------------------------------------------------

    def list_trips(self, user_id: UUID) -> list[dict]:
        rows = self._trips.list_by_user(user_id)
        return [self._serialize_trip(row, expenses=row.expenses) for row in rows]

    def get_trip(self, user_id: UUID, trip_id: UUID) -> dict:
        row = self._trips.get_with_expenses(trip_id, user_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")
        return self._serialize_trip(row, expenses=row.expenses)

    def create_trip(self, user_id: UUID, data: TripCreate) -> dict:
        self._validate_dates(data.data_inicio, data.data_fim)
        trip = Trip(
            nome=data.nome.strip(),
            destino=data.destino.strip() if data.destino else None,
            data_inicio=data.data_inicio,
            data_fim=data.data_fim,
            moeda_base=data.moeda_base.upper(),
            orcamento_total=data.orcamento_total,
            status=data.status.value,
            observacoes=data.observacoes.strip() if data.observacoes else None,
            user_id=user_id,
        )
        created = self._trips.create(trip)
        for spender_id in dict.fromkeys(data.participant_spender_ids):
            self._add_participant(user_id, created.id, spender_id)
        hydrated = self._trips.get_with_expenses(created.id, user_id)
        assert hydrated is not None
        return self._serialize_trip(hydrated, expenses=hydrated.expenses)

    def update_trip(self, user_id: UUID, trip_id: UUID, data: TripUpdate) -> dict:
        row = self._trips.get_by_id(trip_id, user_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")
        if data.status is None:
            self._ensure_mutable(row)
        if data.nome is not None:
            row.nome = data.nome.strip()
        if data.destino is not None:
            row.destino = data.destino.strip() or None
        if data.data_inicio is not None:
            row.data_inicio = data.data_inicio
        if data.data_fim is not None:
            row.data_fim = data.data_fim
        self._validate_dates(row.data_inicio, row.data_fim)
        if data.moeda_base is not None:
            row.moeda_base = data.moeda_base.upper()
        if "orcamento_total" in data.model_fields_set:
            row.orcamento_total = data.orcamento_total
        if data.status is not None:
            row.status = data.status.value
        if data.observacoes is not None:
            row.observacoes = data.observacoes.strip() or None
        self._trips.update(row)
        hydrated = self._trips.get_with_expenses(row.id, user_id)
        assert hydrated is not None
        return self._serialize_trip(hydrated, expenses=hydrated.expenses)

    def delete_trip(self, user_id: UUID, trip_id: UUID) -> None:
        row = self._trips.get_by_id(trip_id, user_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")
        self._trips.delete(row)

    # ------------------------------------------------------------------
    # Participants
    # ------------------------------------------------------------------

    def add_participant(self, user_id: UUID, trip_id: UUID, data: TripParticipantInput) -> dict:
        trip = self._trips.get_by_id(trip_id, user_id)
        if trip is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")
        self._ensure_mutable(trip)
        if data.spender_id is not None:
            self._add_participant(user_id, trip_id, data.spender_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Adicione participantes usando pessoas já cadastradas em Cartões > Pessoas.",
            )
        hydrated = self._trips.get_with_expenses(trip_id, user_id)
        assert hydrated is not None
        return self._serialize_trip(hydrated, expenses=hydrated.expenses)

    def remove_participant(self, user_id: UUID, trip_id: UUID, spender_id: UUID) -> dict:
        trip = self._trips.get_by_id(trip_id, user_id)
        if trip is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")
        self._ensure_mutable(trip)
        participant = self._participants.get(trip_id, spender_id)
        if participant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Participante não encontrado"
            )
        if self._participant_in_use(user_id, trip_id, spender_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não é possível remover: a pessoa tem gastos ou divisões na viagem.",
            )
        self._participants.delete(participant)
        hydrated = self._trips.get_with_expenses(trip_id, user_id)
        assert hydrated is not None
        return self._serialize_trip(hydrated, expenses=hydrated.expenses)

    def _add_participant(self, user_id: UUID, trip_id: UUID, spender_id: UUID) -> TripParticipant:
        sp = self._spenders.get_by_id(spender_id, user_id)
        if sp is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pessoa (spender) não encontrada para este usuário.",
            )
        existing = self._participants.get(trip_id, spender_id)
        if existing is not None:
            return existing
        participant = TripParticipant(trip_id=trip_id, spender_id=spender_id)
        return self._participants.create(participant)

    def _create_local_spender(self, user_id: UUID, nome: str) -> Spender:
        clean = nome.strip()
        if not clean:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nome do participante é obrigatório.",
            )
        row = Spender(nome=clean, user_id=user_id, is_global=False)
        return self._spenders.create(row)

    def _participant_in_use(self, user_id: UUID, trip_id: UUID, spender_id: UUID) -> bool:
        for exp in self._expenses.list_for_trip(trip_id, user_id):
            if exp.paid_by_spender_id == spender_id:
                return True
            for sh in exp.shares:
                if sh.spender_id == spender_id:
                    return True
        return False

    # ------------------------------------------------------------------
    # Expenses
    # ------------------------------------------------------------------

    def list_expenses(self, user_id: UUID, trip_id: UUID) -> list[TripExpense]:
        trip = self._trips.get_by_id(trip_id, user_id)
        if trip is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")
        return self._expenses.list_for_trip(trip_id, user_id)

    def create_expense(
        self, user_id: UUID, trip_id: UUID, data: TripExpenseCreate
    ) -> TripExpense:
        trip = self._trips.get_with_expenses(trip_id, user_id)
        if trip is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")
        self._ensure_mutable(trip)
        participant_ids = {p.spender_id for p in trip.participants}
        if not participant_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Adicione participantes à viagem antes de lançar gastos.",
            )
        if data.paid_by_spender_id not in participant_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O pagador precisa ser um participante da viagem.",
            )
        valor_base = self._compute_valor_base(data.valor, data.taxa_cambio, data.moeda, trip.moeda_base)
        expense = TripExpense(
            descricao=data.descricao.strip(),
            valor=data.valor,
            moeda=data.moeda.upper(),
            taxa_cambio=data.taxa_cambio,
            valor_base=valor_base,
            data=data.data,
            categoria=data.categoria,
            forma_pagamento=data.forma_pagamento,
            paid_by_spender_id=data.paid_by_spender_id,
            observacao=data.observacao.strip() if data.observacao else None,
            trip_id=trip_id,
            user_id=user_id,
        )
        created = self._expenses.create(expense)
        pairs = self._normalize_or_split(
            user_id=user_id,
            shares=data.shares,
            expense_value=data.valor,
            participant_ids=participant_ids,
            paid_by_spender_id=data.paid_by_spender_id,
        )
        self._replace_shares(created.id, pairs)
        loaded = self._expenses.get_by_id(created.id, user_id)
        assert loaded is not None
        return loaded

    def update_expense(
        self, user_id: UUID, expense_id: UUID, data: TripExpenseUpdate
    ) -> TripExpense:
        expense = self._expenses.get_by_id(expense_id, user_id)
        if expense is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gasto não encontrado")
        trip = self._trips.get_with_expenses(expense.trip_id, user_id)
        assert trip is not None
        self._ensure_mutable(trip)
        participant_ids = {p.spender_id for p in trip.participants}

        if data.descricao is not None:
            expense.descricao = data.descricao.strip()
        if data.valor is not None:
            expense.valor = data.valor
        if data.moeda is not None:
            expense.moeda = data.moeda.upper()
        if "taxa_cambio" in data.model_fields_set:
            expense.taxa_cambio = data.taxa_cambio
        if data.data is not None:
            expense.data = data.data
        if data.categoria is not None:
            expense.categoria = data.categoria
        if data.forma_pagamento is not None:
            expense.forma_pagamento = data.forma_pagamento
        if data.paid_by_spender_id is not None:
            if data.paid_by_spender_id not in participant_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="O pagador precisa ser um participante da viagem.",
                )
            expense.paid_by_spender_id = data.paid_by_spender_id
        if "observacao" in data.model_fields_set:
            expense.observacao = data.observacao.strip() if data.observacao else None

        expense.valor_base = self._compute_valor_base(
            expense.valor, expense.taxa_cambio, expense.moeda, trip.moeda_base
        )
        updated = self._expenses.update(expense)

        if data.shares is not None:
            pairs = self._normalize_or_split(
                user_id=user_id,
                shares=data.shares,
                expense_value=updated.valor,
                participant_ids=participant_ids,
                paid_by_spender_id=updated.paid_by_spender_id,
            )
            self._replace_shares(updated.id, pairs)
        elif data.valor is not None:
            self._validate_existing_shares_match_valor(updated)

        loaded = self._expenses.get_by_id(updated.id, user_id)
        assert loaded is not None
        return loaded

    def delete_expense(self, user_id: UUID, expense_id: UUID) -> None:
        expense = self._expenses.get_by_id(expense_id, user_id)
        if expense is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gasto não encontrado")
        trip = self._trips.get_by_id(expense.trip_id, user_id)
        assert trip is not None
        self._ensure_mutable(trip)
        if expense.pushed_expense_id is not None:
            pushed = self._expense_repo.get_by_id(expense.pushed_expense_id, user_id)
            if pushed is not None:
                self._expense_repo.delete(pushed)
        self._expenses.delete(expense)

    # ------------------------------------------------------------------
    # Push to month
    # ------------------------------------------------------------------

    def push_to_month(
        self, user_id: UUID, expense_id: UUID, body: PushToMonthRequest
    ) -> TripExpense:
        expense = self._expenses.get_by_id(expense_id, user_id)
        if expense is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gasto não encontrado")
        if expense.pushed_expense_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este gasto já foi enviado para a despesa do mês.",
            )
        ensure_period_mutable(self._db, user_id, body.period_id)
        category = self._ensure_default_trip_category(user_id)
        new_expense = Expense(
            descricao=expense.descricao,
            valor=expense.valor_base,
            data=expense.data,
            tipo=ExpenseType.VARIABLE,
            recorrente=False,
            pago=body.pago,
            period_id=body.period_id,
            categoria_id=category.id,
            user_id=user_id,
        )
        created_expense = self._expense_repo.create(new_expense)
        if expense.shares:
            scaled = self._scale_shares_to_value(
                [(sh.spender_id, sh.valor) for sh in expense.shares],
                target_total=expense.valor,
                new_total=expense.valor_base,
            )
            rows = [
                ExpenseShare(
                    expense_id=created_expense.id,
                    spender_id=sid,
                    valor=val,
                )
                for sid, val in scaled
            ]
            self._expense_shares.create_many(rows)
        expense.pushed_expense_id = created_expense.id
        self._expenses.update(expense)
        loaded = self._expenses.get_by_id(expense.id, user_id)
        assert loaded is not None
        return loaded

    def _ensure_default_trip_category(self, user_id: UUID) -> Category:
        existing = [
            c
            for c in self._categories.list_by_user(user_id, tipo="expense")
            if c.nome.strip().lower() == DEFAULT_TRIP_CATEGORY_NAME.lower()
        ]
        if existing:
            return existing[0]
        cat = Category(
            nome=DEFAULT_TRIP_CATEGORY_NAME,
            cor=DEFAULT_TRIP_CATEGORY_COLOR,
            tipo="expense",
            user_id=user_id,
        )
        return self._categories.create(cat)

    # ------------------------------------------------------------------
    # Settlement
    # ------------------------------------------------------------------

    def settlement(self, user_id: UUID, trip_id: UUID) -> TripSettlementResponse:
        trip = self._trips.get_with_expenses(trip_id, user_id)
        if trip is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada")

        balances: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0"))
        paid_totals: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0"))
        consumed_totals: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0"))
        names: dict[UUID, str] = {}
        participant_names = {
            participant.spender_id: participant.spender.nome for participant in trip.participants
        }

        for exp in trip.expenses:
            payer_name = participant_names.get(exp.paid_by_spender_id)
            names.setdefault(exp.paid_by_spender_id, payer_name or "?")
            paid_totals[exp.paid_by_spender_id] += exp.valor
            balances[exp.paid_by_spender_id] += exp.valor
            for share in exp.shares:
                consumed_totals[share.spender_id] += share.valor
                balances[share.spender_id] -= share.valor
                share_name = participant_names.get(share.spender_id)
                names.setdefault(share.spender_id, share_name or (share.spender.nome if share.spender else "?"))

        saldos = [
            TripPersonTotal(
                spender_id=sid,
                spender_nome=names.get(sid, "?"),
                total_pago=paid_totals[sid].quantize(CENT),
                total_consumido=consumed_totals[sid].quantize(CENT),
                saldo=balances[sid].quantize(CENT),
            )
            for sid in balances
        ]
        saldos.sort(key=lambda r: r.spender_nome.lower())

        transferencias = self._minimal_transfers(
            {sid: bal.quantize(CENT) for sid, bal in balances.items()}, names
        )

        return TripSettlementResponse(
            trip_id=trip.id,
            moeda_base=trip.moeda_base,
            saldos=saldos,
            transferencias=transferencias,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_mutable(self, trip: Trip) -> None:
        if trip.status == TripStatus.CLOSED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Viagem encerrada: alterações não são permitidas. Reabra mudando o status.",
            )

    @staticmethod
    def _validate_dates(inicio, fim) -> None:
        if inicio is not None and fim is not None and fim < inicio:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A data de fim não pode ser anterior à data de início.",
            )

    def _normalize_or_split(
        self,
        *,
        user_id: UUID,
        shares: list[TripExpenseShareInput] | None,
        expense_value: Decimal,
        participant_ids: set[UUID],
        paid_by_spender_id: UUID,
    ) -> list[tuple[UUID, Decimal]]:
        # Sem divisão explícita: reparte igualmente entre todos os participantes da viagem.
        if shares is None or len(shares) == 0:
            return self._even_split(participant_ids, expense_value)
        return self._normalize_share_pairs(
            user_id=user_id,
            shares=shares,
            expense_value=expense_value,
            participant_ids=participant_ids,
        )

    def _normalize_share_pairs(
        self,
        *,
        user_id: UUID,
        shares: list[TripExpenseShareInput],
        expense_value: Decimal,
        participant_ids: set[UUID],
    ) -> list[tuple[UUID, Decimal]]:
        pairs: list[tuple[UUID, Decimal]] = []
        seen: set[UUID] = set()
        for row in shares:
            if row.spender_id in seen:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Uma mesma pessoa apareceu mais de uma vez na divisão.",
                )
            seen.add(row.spender_id)
            if row.spender_id not in participant_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Há pessoas na divisão que não são participantes da viagem.",
                )
            sp = self._spenders.get_by_id(row.spender_id, user_id)
            if sp is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Pessoa (spender) não encontrada.",
                )
            pairs.append((row.spender_id, row.valor))
        total = sum((v for _, v in pairs), Decimal("0"))
        if abs(total - expense_value) > SHARE_SUM_TOLERANCE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A soma das partes ({total}) deve ser igual ao valor do gasto ({expense_value}).",
            )
        return pairs

    @staticmethod
    def _even_split(participant_ids: set[UUID], total: Decimal) -> list[tuple[UUID, Decimal]]:
        ordered = sorted(participant_ids, key=str)
        n = len(ordered)
        if n == 0:
            return []
        per = (total / Decimal(n)).quantize(CENT, rounding=ROUND_HALF_UP)
        pairs: list[tuple[UUID, Decimal]] = []
        running = Decimal("0")
        for i, sid in enumerate(ordered):
            if i < n - 1:
                pairs.append((sid, per))
                running += per
            else:
                pairs.append((sid, (total - running).quantize(CENT, rounding=ROUND_HALF_UP)))
        return pairs

    def _replace_shares(self, expense_id: UUID, pairs: list[tuple[UUID, Decimal]]) -> None:
        self._shares.delete_for_expense(expense_id)
        if not pairs:
            return
        rows = [
            TripExpenseShare(trip_expense_id=expense_id, spender_id=sid, valor=valor)
            for sid, valor in pairs
        ]
        self._shares.create_many(rows)

    def _validate_existing_shares_match_valor(self, expense: TripExpense) -> None:
        loaded = self._shares.list_for_expense(expense.id)
        if not loaded:
            return
        total = sum((sh.valor for sh in loaded), Decimal("0"))
        if abs(total - expense.valor) > SHARE_SUM_TOLERANCE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A divisão não confere com o novo valor. Atualize as partes.",
            )

    @staticmethod
    def _compute_valor_base(
        valor: Decimal, taxa_cambio: Decimal | None, moeda: str, moeda_base: str
    ) -> Decimal:
        if moeda.upper() == moeda_base.upper() or taxa_cambio is None:
            return valor.quantize(CENT, rounding=ROUND_HALF_UP)
        return (valor * taxa_cambio).quantize(CENT, rounding=ROUND_HALF_UP)

    @staticmethod
    def _scale_shares_to_value(
        pairs: list[tuple[UUID, Decimal]],
        *,
        target_total: Decimal,
        new_total: Decimal,
    ) -> list[tuple[UUID, Decimal]]:
        if not pairs:
            return []
        if target_total == 0:
            return [(sid, Decimal("0.00")) for sid, _ in pairs]
        out: list[tuple[UUID, Decimal]] = []
        acc = Decimal("0")
        n = len(pairs)
        for i, (sid, val) in enumerate(pairs):
            if i == n - 1:
                part = (new_total - acc).quantize(CENT, rounding=ROUND_HALF_UP)
            else:
                part = (val / target_total * new_total).quantize(CENT, rounding=ROUND_HALF_UP)
                acc += part
            out.append((sid, part))
        return out

    @staticmethod
    def _minimal_transfers(
        balances: dict[UUID, Decimal], names: dict[UUID, str]
    ) -> list[TripSettlementTransfer]:
        creditors: list[list] = []
        debtors: list[list] = []
        for sid, bal in balances.items():
            if bal > Decimal("0.00"):
                creditors.append([sid, bal])
            elif bal < Decimal("0.00"):
                debtors.append([sid, -bal])
        creditors.sort(key=lambda x: x[1], reverse=True)
        debtors.sort(key=lambda x: x[1], reverse=True)

        transfers: list[TripSettlementTransfer] = []
        i = j = 0
        while i < len(debtors) and j < len(creditors):
            d_sid, d_val = debtors[i]
            c_sid, c_val = creditors[j]
            amount = min(d_val, c_val)
            if amount > Decimal("0.00"):
                transfers.append(
                    TripSettlementTransfer(
                        from_spender_id=d_sid,
                        from_spender_nome=names.get(d_sid, "?"),
                        to_spender_id=c_sid,
                        to_spender_nome=names.get(c_sid, "?"),
                        valor=amount.quantize(CENT),
                    )
                )
            debtors[i][1] = d_val - amount
            creditors[j][1] = c_val - amount
            if debtors[i][1] <= Decimal("0.00"):
                i += 1
            if creditors[j][1] <= Decimal("0.00"):
                j += 1
        return transfers

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _serialize_trip(self, trip: Trip, *, expenses: list[TripExpense] | None) -> dict:
        expenses = expenses or []
        total_gasto = sum((e.valor_base for e in expenses), Decimal("0"))
        cat_totals: dict[TripCategory, Decimal] = defaultdict(lambda: Decimal("0"))
        paid: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0"))
        consumed: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0"))
        consumed_by_cat: dict[UUID, dict[TripCategory, Decimal]] = defaultdict(
            lambda: defaultdict(lambda: Decimal("0"))
        )

        # use base currency to keep totals consistent in the trip's moeda_base
        for exp in expenses:
            cat_totals[exp.categoria] += exp.valor_base
            paid[exp.paid_by_spender_id] += exp.valor_base
            target_total = exp.valor or Decimal("0")
            scale = (
                (exp.valor_base / target_total)
                if target_total != Decimal("0")
                else Decimal("0")
            )
            for sh in exp.shares:
                share_base = (sh.valor * scale).quantize(CENT, rounding=ROUND_HALF_UP)
                consumed[sh.spender_id] += share_base
                consumed_by_cat[sh.spender_id][exp.categoria] += share_base

        names: dict[UUID, str] = {}
        for p in trip.participants:
            names[p.spender_id] = p.spender.nome

        total_por_pessoa = []
        for sid in dict.fromkeys(list(names.keys()) + list(paid.keys()) + list(consumed.keys())):
            total_por_pessoa.append(
                TripPersonTotal(
                    spender_id=sid,
                    spender_nome=names.get(sid, "?"),
                    total_pago=paid.get(sid, Decimal("0")).quantize(CENT),
                    total_consumido=consumed.get(sid, Decimal("0")).quantize(CENT),
                    saldo=(paid.get(sid, Decimal("0")) - consumed.get(sid, Decimal("0"))).quantize(CENT),
                )
            )
        total_por_pessoa.sort(key=lambda r: r.spender_nome.lower())

        total_por_categoria = [
            TripCategoryTotal(categoria=cat, total=val.quantize(CENT))
            for cat, val in cat_totals.items()
        ]
        total_por_categoria.sort(key=lambda r: r.total, reverse=True)

        consumo_por_pessoa: list[TripPersonConsumptionBreakdown] = []
        for sid in sorted(
            consumed_by_cat.keys(),
            key=lambda x: names.get(x, "?").lower(),
        ):
            cats = consumed_by_cat[sid]
            person_total = sum(cats.values(), Decimal("0")).quantize(CENT)
            if person_total <= Decimal("0"):
                continue
            por_categoria_lines = [
                TripPersonCategoryLine(categoria=c, total=v.quantize(CENT))
                for c, v in sorted(
                    cats.items(),
                    key=lambda item: (-item[1], item[0].value),
                )
            ]
            consumo_por_pessoa.append(
                TripPersonConsumptionBreakdown(
                    spender_id=sid,
                    spender_nome=names.get(sid, "?"),
                    total=person_total,
                    por_categoria=por_categoria_lines,
                )
            )

        participants_resp = [
            {"spender_id": p.spender_id, "spender_nome": p.spender.nome}
            for p in trip.participants
        ]

        return {
            "id": trip.id,
            "nome": trip.nome,
            "destino": trip.destino,
            "data_inicio": trip.data_inicio,
            "data_fim": trip.data_fim,
            "moeda_base": trip.moeda_base,
            "orcamento_total": trip.orcamento_total,
            "status": trip.status,
            "observacoes": trip.observacoes,
            "user_id": trip.user_id,
            "participants": participants_resp,
            "total_gasto": total_gasto.quantize(CENT),
            "total_por_categoria": total_por_categoria,
            "total_por_pessoa": total_por_pessoa,
            "consumo_por_pessoa": consumo_por_pessoa,
            "created_at": trip.created_at,
            "updated_at": trip.updated_at,
        }


# Re-exports for convenience
__all__ = [
    "TripService",
    "PaymentMethod",
    "TripCategory",
    "TripStatus",
]
