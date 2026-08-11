from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.expenses.enums import ExpenseType, RecurrenceValueMode
from app.expenses.model import Expense
from app.expenses.schemas import ExpenseCreate, ExpenseShareInput, ExpenseUpdate, GenerateInstallmentsRequest
from app.models.installment import Installment
from app.models.expense_share import ExpenseShare
from app.repositories.category_repository import CategoryRepository
from app.repositories.expense_repository import ExpenseRepository
from app.repositories.expense_share_repository import ExpenseShareRepository
from app.repositories.installment_repository import InstallmentRepository
from app.repositories.period_repository import PeriodRepository
from app.repositories.spender_repository import SpenderRepository
from app.services.card_transaction_share_logic import SHARE_SUM_TOLERANCE, scale_shares_to_line
from app.services.date_utils import date_in_month
from app.services.period_mutability import ensure_period_mutable
from app.services.period_service import PeriodService


class ExpenseService:
    """Regras de negócio para despesas e parcelas (escopo por `user_id`)."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._expenses = ExpenseRepository(db)
        self._periods = PeriodRepository(db)
        self._categories = CategoryRepository(db)
        self._installments = InstallmentRepository(db)
        self._spenders = SpenderRepository(db)
        self._shares = ExpenseShareRepository(db)

    def _normalize_share_pairs(
        self,
        user_id: UUID,
        shares: list[ExpenseShareInput] | None,
        expense_value: Decimal,
        *,
        existing_pago_by_spender: dict[UUID, bool] | None = None,
    ) -> list[tuple[UUID, Decimal, bool]]:
        if not shares:
            return []
        pairs: list[tuple[UUID, Decimal, bool]] = []
        for row in shares:
            sp = self._spenders.get_by_id(row.spender_id, user_id)
            if sp is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Pessoa (spender) não encontrada",
                )
            # Se o cliente não enviou pago explicitamente no sentido de update parcial,
            # ExpenseShareInput sempre tem pago (default False). Preserve existing when
            # the input still has default False and we have a previous flag.
            pago = row.pago
            if existing_pago_by_spender is not None and row.spender_id in existing_pago_by_spender:
                # Prefer explicit True from client; otherwise keep existing if client sent False
                # without intending to clear — actually client always sends pago in new UI.
                # Preserve when creating from amount-only payloads that default pago=False:
                # only preserve if the field wasn't in the model dump with pago set...
                # Simplest rule from plan: use input pago if provided; preserve if recreating
                # from valor-only scaling. For PATCH shares from frontend with amounts only,
                # preserve existing pago by spender.
                if "pago" not in row.model_fields_set:
                    pago = existing_pago_by_spender[row.spender_id]
            pairs.append((row.spender_id, row.valor, pago))
        total = sum((v for _, v, _ in pairs), Decimal("0"))
        if abs(total - expense_value) > SHARE_SUM_TOLERANCE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A soma das partes ({total}) deve ser igual ao valor da despesa ({expense_value}).",
            )
        return pairs

    def _replace_shares(self, expense_id: UUID, pairs: list[tuple[UUID, Decimal, bool]]) -> None:
        self._shares.delete_for_expense(expense_id)
        if not pairs:
            return
        rows = [
            ExpenseShare(
                expense_id=expense_id,
                spender_id=spender_id,
                valor=value,
                pago=pago,
            )
            for spender_id, value, pago in pairs
        ]
        self._shares.create_many(rows)

    def _sync_expense_pago_from_shares(self, expense: Expense) -> Expense:
        loaded = self._shares.list_for_expense(expense.id)
        if not loaded:
            return expense
        expense.pago = all(sh.pago for sh in loaded)
        return self._expenses.update(expense)

    def _validate_existing_shares_match_valor(self, expense: Expense) -> None:
        loaded = self._shares.list_for_expense(expense.id)
        if not loaded:
            return
        total = sum((sh.valor for sh in loaded), Decimal("0"))
        if abs(total - expense.valor) > SHARE_SUM_TOLERANCE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A divisão entre pessoas não bate com o novo valor. Atualize as partes.",
            )

    def _replicate_fixed_to_future_periods(
        self,
        user_id: UUID,
        source: Expense,
        *,
        recurrence_value_mode: RecurrenceValueMode,
        share_pairs: list[tuple[UUID, Decimal, bool]],
    ) -> None:
        period = self._periods.get_by_id(source.period_id, user_id)
        if period is None:
            return
        future = self._periods.periods_after(user_id, period.ano, period.mes)
        orig_day = source.data.day
        recurring_value = (
            source.valor
            if recurrence_value_mode == RecurrenceValueMode.SAME_VALUE
            else Decimal("0")
        )
        for fp in future:
            existing = self._expenses.find_fixed_by_descricao_categoria_period(
                user_id, fp.id, source.categoria_id, source.descricao
            )
            if existing is not None:
                continue
            ensure_period_mutable(self._db, user_id, fp.id)
            d = date_in_month(fp.ano, fp.mes, orig_day)
            clone = Expense(
                descricao=source.descricao,
                valor=recurring_value,
                data=d,
                tipo=source.tipo,
                recorrente=False,
                pago=False,
                period_id=fp.id,
                categoria_id=source.categoria_id,
                user_id=user_id,
            )
            cloned = self._expenses.create(clone)
            if recurrence_value_mode == RecurrenceValueMode.SAME_VALUE:
                unpaid_pairs = [(sid, val, False) for sid, val, _ in share_pairs]
                self._replace_shares(cloned.id, unpaid_pairs)

    def _ensure_period_and_category(
        self, user_id: UUID, period_id: UUID, categoria_id: UUID
    ) -> None:
        p = self._periods.get_by_id(period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        c = self._categories.get_by_id(categoria_id, user_id)
        if c is None or c.tipo != "expense":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid expense category",
            )
        ensure_period_mutable(self._db, user_id, period_id)

    def create(self, user_id: UUID, data: ExpenseCreate) -> Expense:
        if data.recorrente and data.tipo != ExpenseType.FIXED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recorrente permitido apenas para despesa fixa",
            )
        self._ensure_period_and_category(user_id, data.period_id, data.categoria_id)
        pairs = self._normalize_share_pairs(user_id, data.shares, data.valor)
        if pairs:
            # Com divisão, expense.pago deriva das shares.
            if data.pago:
                pairs = [(sid, val, True) for sid, val, _ in pairs]
            expense_pago = all(pago for _, _, pago in pairs)
        else:
            expense_pago = data.pago
        e = Expense(
            descricao=data.descricao,
            valor=data.valor,
            data=data.data,
            tipo=data.tipo,
            recorrente=data.recorrente,
            pago=expense_pago,
            period_id=data.period_id,
            categoria_id=data.categoria_id,
            user_id=user_id,
        )
        e = self._expenses.create(e)
        self._replace_shares(e.id, pairs)
        if data.recorrente:
            self._replicate_fixed_to_future_periods(
                user_id,
                e,
                recurrence_value_mode=data.recurrence_value_mode,
                share_pairs=pairs,
            )
        loaded = self._expenses.get_by_id(e.id, user_id)
        assert loaded is not None
        return loaded

    def update(self, user_id: UUID, expense_id: UUID, data: ExpenseUpdate) -> Expense:
        e = self._expenses.get_by_id(expense_id, user_id)
        if e is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
        ensure_period_mutable(self._db, user_id, e.period_id)
        old_valor = e.valor
        if data.descricao is not None:
            e.descricao = data.descricao
        if data.valor is not None:
            e.valor = data.valor
        if data.data is not None:
            e.data = data.data
        if data.tipo is not None:
            e.tipo = data.tipo
        if data.pago is not None:
            e.pago = data.pago
        if data.recorrente is not None:
            effective_tipo = data.tipo if data.tipo is not None else e.tipo
            if data.recorrente and effective_tipo != ExpenseType.FIXED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Recorrente permitido apenas para despesa fixa",
                )
            e.recorrente = data.recorrente
        if data.period_id is not None:
            self._ensure_period_and_category(user_id, data.period_id, e.categoria_id)
            e.period_id = data.period_id
        if data.categoria_id is not None:
            self._ensure_period_and_category(user_id, e.period_id, data.categoria_id)
            e.categoria_id = data.categoria_id
        updated = self._expenses.update(e)

        existing_shares = self._shares.list_for_expense(updated.id)
        existing_pago = {sh.spender_id: sh.pago for sh in existing_shares}

        if data.shares is not None:
            pairs = self._normalize_share_pairs(
                user_id,
                data.shares,
                updated.valor,
                existing_pago_by_spender=existing_pago,
            )
            self._replace_shares(updated.id, pairs)
            reloaded = self._expenses.get_by_id(updated.id, user_id)
            assert reloaded is not None
            updated = self._sync_expense_pago_from_shares(reloaded)
        elif data.valor is not None and data.valor != old_valor:
            if existing_shares:
                template = [(sh.spender_id, sh.valor) for sh in existing_shares]
                scaled = scale_shares_to_line(template, updated.valor, old_valor)
                scaled_with_pago = [
                    (sid, val, existing_pago.get(sid, False)) for sid, val in scaled
                ]
                self._replace_shares(updated.id, scaled_with_pago)
                reloaded = self._expenses.get_by_id(updated.id, user_id)
                assert reloaded is not None
                updated = reloaded
        elif data.pago is not None and existing_shares:
            # PATCH expense.pago com divisão → aplica a todas as shares.
            self.set_all_shares_paid(user_id, updated.id, data.pago)
            reloaded = self._expenses.get_by_id(updated.id, user_id)
            assert reloaded is not None
            updated = reloaded

        if data.recorrente:
            loaded_shares = self._shares.list_for_expense(updated.id)
            share_pairs = [(sh.spender_id, sh.valor, False) for sh in loaded_shares]
            recurrence_mode = (
                data.recurrence_value_mode
                if data.recurrence_value_mode is not None
                else RecurrenceValueMode.SAME_VALUE
            )
            self._replicate_fixed_to_future_periods(
                user_id,
                updated,
                recurrence_value_mode=recurrence_mode,
                share_pairs=share_pairs,
            )
            reloaded = self._expenses.get_by_id(updated.id, user_id)
            assert reloaded is not None
            return reloaded
        return updated

    def delete(self, user_id: UUID, expense_id: UUID) -> None:
        e = self._expenses.get_by_id(expense_id, user_id)
        if e is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
        ensure_period_mutable(self._db, user_id, e.period_id)
        self._expenses.delete(e)

    def mark_paid(self, user_id: UUID, expense_id: UUID, *, pago: bool = True) -> Expense:
        e = self._expenses.get_by_id(expense_id, user_id)
        if e is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
        ensure_period_mutable(self._db, user_id, e.period_id)
        loaded_shares = self._shares.list_for_expense(e.id)
        if loaded_shares:
            return self.set_all_shares_paid(user_id, expense_id, pago)
        e.pago = pago
        return self._expenses.update(e)

    def set_share_paid(
        self, user_id: UUID, expense_id: UUID, spender_id: UUID, *, pago: bool
    ) -> Expense:
        e = self._expenses.get_by_id(expense_id, user_id)
        if e is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
        ensure_period_mutable(self._db, user_id, e.period_id)
        shares = self._shares.list_for_expense(e.id)
        target = next((sh for sh in shares if sh.spender_id == spender_id), None)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parte da pessoa não encontrada nesta despesa",
            )
        target.pago = pago
        self._db.add(target)
        self._db.flush()
        self._sync_expense_pago_from_shares(e)
        loaded = self._expenses.get_by_id(expense_id, user_id)
        assert loaded is not None
        return loaded

    def set_all_shares_paid(self, user_id: UUID, expense_id: UUID, pago: bool) -> Expense:
        e = self._expenses.get_by_id(expense_id, user_id)
        if e is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
        ensure_period_mutable(self._db, user_id, e.period_id)
        shares = self._shares.list_for_expense(e.id)
        if not shares:
            e.pago = pago
            return self._expenses.update(e)
        for sh in shares:
            sh.pago = pago
            self._db.add(sh)
        self._db.flush()
        e.pago = pago
        self._expenses.update(e)
        loaded = self._expenses.get_by_id(expense_id, user_id)
        assert loaded is not None
        return loaded

    def list_by_period(self, user_id: UUID, period_id: UUID) -> list[Expense]:
        p = self._periods.get_by_id(period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        return self._shares.list_expenses_with_shares_for_period(user_id, period_id)

    def list_by_category(self, user_id: UUID, categoria_id: UUID) -> list[Expense]:
        c = self._categories.get_by_id(categoria_id, user_id)
        if c is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        return self._shares.list_expenses_with_shares_for_category(user_id, categoria_id)

    def get(self, user_id: UUID, expense_id: UUID) -> Expense:
        e = self._expenses.get_by_id(expense_id, user_id)
        if e is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
        return e

    def generate_installments(
        self, user_id: UUID, expense_id: UUID, body: GenerateInstallmentsRequest
    ) -> list[Installment]:
        e = self._expenses.get_by_id(expense_id, user_id)
        if e is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
        ensure_period_mutable(self._db, user_id, e.period_id)
        seq = PeriodService(self._db).ensure_calendar_periods_from_start(
            user_id, body.start_period_id, body.total_parcelas
        )
        for sp in seq:
            ensure_period_mutable(self._db, user_id, sp.id)
        total_val = e.valor
        n = body.total_parcelas
        per = (total_val / Decimal(n)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        items: list[Installment] = []
        running = Decimal("0")
        for i in range(n):
            val = (
                per
                if i < n - 1
                else (total_val - running).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            )
            running += val
            items.append(
                Installment(
                    numero=i + 1,
                    total=n,
                    valor=val,
                    pago=False,
                    expense_id=e.id,
                    period_id=seq[i].id,
                )
            )
        return self._installments.create_many(items)
