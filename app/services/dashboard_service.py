from datetime import date
from decimal import Decimal
from typing import Any, Callable
from uuid import UUID
import calendar

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.card import Card
from app.models.goal import Goal
from app.repositories.card_repository import CardRepository
from app.repositories.card_transaction_repository import CardTransactionRepository
from app.repositories.card_transaction_share_repository import CardTransactionShareRepository
from app.repositories.expense_repository import ExpenseRepository
from app.repositories.goal_repository import GoalRepository
from app.repositories.income_repository import IncomeRepository
from app.repositories.period_repository import PeriodRepository
from app.repositories.user_repository import UserRepository
from app.repositories.debtor_repository import DebtorRepository
from app.schemas.dashboard_schema import (
    CardPeriodTotal,
    DashboardSummary,
    ExpenseCategoryBreakdown,
    FixedExpensePeriodLine,
    ExpensePersonCategoryBreakdown,
    ExpensePersonCategoryBreakdownRow,
    ExpensePersonBreakdown,
    GoalProgressRow,
    PersonCardUsageRow,
    PersonDebtorUsageRow,
    PersonFixedExpenseUsageRow,
    PersonUsageDashboardRow,
    PersonInstallmentDashboardRow,
    PersonInstallmentPurchaseRow,
)
from app.services.category_spending_merge import merge_expense_and_card_category_rows
from app.services.dashboard_cache import DashboardCache
from app.services.statement_parse_service import extract_parcela_from_description


class DashboardService:
    """Agregações do dashboard por `period_id` e `user_id`."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._periods = PeriodRepository(db)
        self._users = UserRepository(db)
        self._incomes = IncomeRepository(db)
        self._expenses = ExpenseRepository(db)
        self._cards = CardRepository(db)
        self._card_txs = CardTransactionRepository(db)
        self._card_tx_shares = CardTransactionShareRepository(db)
        self._goals = GoalRepository(db)
        self._debtors = DebtorRepository(db)

    def _ensure_period(self, user_id: UUID, period_id: UUID) -> None:
        p = self._periods.get_by_id(period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")

    def _monthly_balance(self, user_id: UUID, period_id: UUID) -> tuple[Decimal, Decimal, Decimal]:
        """Retorna (total_income, total_expenses, monthly_balance)."""
        total_income = Decimal(str(self._incomes.sum_by_period(user_id, period_id)))
        exp = self._fixed_expense_sum_for_me(user_id, period_id, unpaid_only=False)
        card = self._card_sum_for_me(user_id, period_id, unpaid_only=False)
        total_expenses = exp + card
        monthly_balance = total_income - total_expenses
        return total_income, total_expenses, monthly_balance

    def _expenses_by_category(self, user_id: UUID, period_id: UUID) -> list[ExpenseCategoryBreakdown]:
        exp_rows = self._expenses.aggregates_by_category_period(user_id, period_id)
        card_rows = self._card_aggregates_by_category_for_me(user_id, period_id)
        merged = merge_expense_and_card_category_rows(exp_rows, card_rows)
        breakdown = [
            ExpenseCategoryBreakdown(
                categoria_id=cid,
                categoria_nome=nome,
                total=amt,
            )
            for cid, nome, amt in merged
        ]
        breakdown.sort(key=lambda x: x.total, reverse=True)
        return breakdown

    def _get_me_spender_id(self, user_id: UUID) -> UUID | None:
        user = self._users.get_by_id(user_id)
        return user.me_spender_id if user is not None else None

    def _card_sum_for_me(self, user_id: UUID, period_id: UUID, *, unpaid_only: bool) -> Decimal:
        me_spender_id = self._get_me_spender_id(user_id)
        txs = self._card_tx_shares.list_transactions_with_shares_for_period(user_id, period_id)
        total = Decimal("0")
        for tx in txs:
            if tx.shares:
                if me_spender_id is None:
                    continue
                for sh in tx.shares:
                    if sh.spender_id != me_spender_id:
                        continue
                    if unpaid_only and bool(getattr(sh, "pago", False)):
                        continue
                    total += sh.valor
                continue
            # Dashboard pessoal: sem divisão explícita não entra na métrica "EU".
            continue
        return total

    def _card_aggregates_by_category_for_me(
        self, user_id: UUID, period_id: UUID
    ) -> list[tuple[UUID, str, float]]:
        me_spender_id = self._get_me_spender_id(user_id)
        txs = self._card_tx_shares.list_transactions_with_shares_for_period(user_id, period_id)
        totals: dict[tuple[UUID, str], Decimal] = {}
        for tx in txs:
            if tx.categoria_id is None or tx.categoria is None:
                continue
            key = (tx.categoria_id, tx.categoria.nome)
            current = totals.get(key, Decimal("0"))
            if tx.shares:
                if me_spender_id is None:
                    continue
                me_value = sum((sh.valor for sh in tx.shares if sh.spender_id == me_spender_id), Decimal("0"))
                totals[key] = current + me_value
                continue
            # Dashboard pessoal: transação sem divisão não compõe categoria da pessoa "EU".
            continue
        return [(cid, nome, float(amount)) for (cid, nome), amount in totals.items()]

    def _fixed_expense_sum_for_me(self, user_id: UUID, period_id: UUID, *, unpaid_only: bool) -> Decimal:
        me_spender_id = self._get_me_spender_id(user_id)
        if me_spender_id is None:
            return Decimal("0")
        expenses = self._expenses.list_fixed_by_period(user_id, period_id)
        total = Decimal("0")
        for exp in expenses:
            if exp.shares:
                for sh in exp.shares:
                    if sh.spender_id != me_spender_id:
                        continue
                    if unpaid_only and bool(getattr(sh, "pago", False)):
                        continue
                    total += sh.valor
                continue
            # Dashboard pessoal: despesa fixa sem divisão não entra na métrica "EU".
            continue
        return total

    def _goal_progress(self, user_id: UUID) -> tuple[list[GoalProgressRow], Decimal]:
        """Lista de progresso por meta e soma de valor_atual."""
        goal_rows: list[Goal] = self._goals.list_by_user(user_id)
        progress_list: list[GoalProgressRow] = []
        goals_total = Decimal("0")
        for g in goal_rows:
            goals_total += g.valor_atual
            pct = (
                float((g.valor_atual / g.valor_meta * Decimal(100)))
                if g.valor_meta > 0
                else 0.0
            )
            progress_list.append(
                GoalProgressRow(
                    goal_id=g.id,
                    nome=g.nome,
                    tipo=g.tipo,
                    valor_meta=g.valor_meta,
                    valor_atual=g.valor_atual,
                    progress_percent=round(pct, 2),
                )
            )
        progress_list.sort(key=lambda x: x.progress_percent, reverse=True)
        return progress_list, goals_total

    def _expenses_by_person(self, user_id: UUID, period_id: UUID) -> list[ExpensePersonBreakdown]:
        """Agrega gastos do cartão por pessoa via rateio; sem rateio vira 'Sem pessoa'."""
        txs = self._card_tx_shares.list_transactions_with_shares_for_period(user_id, period_id)
        totals: dict[UUID | None, tuple[str, Decimal]] = {}

        def add_total(person_id: UUID | None, person_name: str, amount: Decimal) -> None:
            current_name, current_amount = totals.get(person_id, (person_name, Decimal("0")))
            totals[person_id] = (current_name, current_amount + amount)

        for tx in txs:
            if tx.shares:
                for sh in tx.shares:
                    spender_name = sh.spender.nome if sh.spender else "Pessoa removida"
                    add_total(sh.spender_id, spender_name, sh.valor)
                continue

            add_total(None, "Sem pessoa", tx.valor)

        out = [
            ExpensePersonBreakdown(
                pessoa_id=person_id,
                pessoa_nome=person_name,
                total=amount,
            )
            for person_id, (person_name, amount) in totals.items()
        ]
        out.sort(key=lambda x: x.total, reverse=True)
        return out

    def _expenses_by_person_category(
        self, user_id: UUID, period_id: UUID
    ) -> list[ExpensePersonCategoryBreakdown]:
        """Agrega gastos de cartão por pessoa e categoria no período."""
        txs = self._card_tx_shares.list_transactions_with_shares_for_period(user_id, period_id)
        by_person_category: dict[UUID | None, dict[UUID | None, Decimal]] = {}
        person_names: dict[UUID | None, str] = {}
        category_names: dict[UUID | None, str] = {}

        def add_value(
            person_id: UUID | None,
            person_name: str,
            category_id: UUID | None,
            category_name: str,
            amount: Decimal,
        ) -> None:
            person_names[person_id] = person_name
            category_names[category_id] = category_name
            by_person_category.setdefault(person_id, {})
            prev = by_person_category[person_id].get(category_id, Decimal("0"))
            by_person_category[person_id][category_id] = prev + amount

        for tx in txs:
            category_id = tx.categoria_id
            category_name = tx.categoria.nome if tx.categoria else "Sem categoria"
            if tx.shares:
                for sh in tx.shares:
                    spender_name = sh.spender.nome if sh.spender else "Pessoa removida"
                    add_value(sh.spender_id, spender_name, category_id, category_name, sh.valor)
                continue
            add_value(None, "Sem pessoa", category_id, category_name, tx.valor)

        out: list[ExpensePersonCategoryBreakdown] = []
        for person_id, category_totals in by_person_category.items():
            categories = [
                ExpensePersonCategoryBreakdownRow(
                    categoria_id=category_id,
                    categoria_nome=category_names[category_id],
                    total=amount,
                )
                for category_id, amount in category_totals.items()
            ]
            categories.sort(key=lambda x: x.total, reverse=True)
            person_total = sum((row.total for row in categories), Decimal("0"))
            out.append(
                ExpensePersonCategoryBreakdown(
                    pessoa_id=person_id,
                    pessoa_nome=person_names[person_id],
                    total=person_total,
                    categorias=categories,
                )
            )

        out.sort(key=lambda x: x.total, reverse=True)
        return out

    def _person_installments(
        self, user_id: UUID, period_id: UUID
    ) -> tuple[list[PersonInstallmentDashboardRow], Decimal]:
        """Lista compras parceladas por pessoa e retorna total de parcelas do mês."""
        txs = self._card_tx_shares.list_transactions_with_shares_for_period(user_id, period_id)
        card_names = {c.id: c.nome for c in self._cards.list_by_user(user_id)}
        period = self._periods.get_by_id(period_id, user_id)
        if period is None:
            return [], Decimal("0")
        by_person: dict[UUID | None, dict[str, object]] = {}
        total_installments_month = Decimal("0")

        def add_months(base_date: date, months: int) -> date:
            month_index = (base_date.month - 1) + months
            target_year = base_date.year + (month_index // 12)
            target_month = (month_index % 12) + 1
            target_day = min(base_date.day, calendar.monthrange(target_year, target_month)[1])
            return date(target_year, target_month, target_day)

        def period_based_date(day: int) -> date:
            safe_day = min(day, calendar.monthrange(period.ano, period.mes)[1])
            return date(period.ano, period.mes, safe_day)

        def ensure_person(person_id: UUID | None, person_name: str) -> dict[str, object]:
            current = by_person.get(person_id)
            if current is None:
                current = {"name": person_name, "purchases": {}}
                by_person[person_id] = current
            return current

        def add_purchase(
            person_id: UUID | None,
            person_name: str,
            tx_date: date,
            tx_desc: str,
            card_id: UUID,
            installment_value: Decimal,
            installment_total: int,
            installment_number: int,
        ) -> None:
            nonlocal total_installments_month
            person_entry = ensure_person(person_id, person_name)
            purchases = person_entry["purchases"]
            base_desc = extract_parcela_from_description(tx_desc)[0].strip()
            group_key = f"{card_id}:{base_desc.lower()}:{installment_total}:{installment_number}"
            current = purchases.get(group_key)
            total_installments_month += installment_value
            if current is None:
                purchases[group_key] = {
                    "compra_id": group_key,
                    "card_id": card_id,
                    "card_nome": card_names.get(card_id, "Cartao removido"),
                    "descricao": base_desc or tx_desc,
                    "valor_parcela": installment_value,
                    "parcela_atual": installment_number,
                    "total_parcelas": installment_total,
                    # Usa o mês/ano do período selecionado como base para evitar datas importadas incoerentes.
                    "ate_data": add_months(
                        period_based_date(tx_date.day),
                        max(0, installment_total - installment_number),
                    ),
                }
                return
            current["valor_parcela"] = current["valor_parcela"] + installment_value

        for tx in txs:
            if tx.installment_total <= 1:
                continue
            if tx.shares:
                for sh in tx.shares:
                    spender_name = sh.spender.nome if sh.spender else "Pessoa removida"
                    add_purchase(
                        sh.spender_id,
                        spender_name,
                        tx.data,
                        tx.descricao,
                        tx.card_id,
                        sh.valor,
                        tx.installment_total,
                        tx.installment_number,
                    )
                continue
            add_purchase(
                None,
                "Sem pessoa",
                tx.data,
                tx.descricao,
                tx.card_id,
                tx.valor,
                tx.installment_total,
                tx.installment_number,
            )

        out = [
            PersonInstallmentDashboardRow(
                pessoa_id=person_id,
                pessoa_nome=person_data["name"],
                compras_parceladas=len(person_data["purchases"]),
                total_parcelas_mes=sum(
                    (purchase["valor_parcela"] for purchase in person_data["purchases"].values()),
                    Decimal("0"),
                ),
                compras=[
                    PersonInstallmentPurchaseRow(
                        compra_id=purchase["compra_id"],
                        card_id=purchase["card_id"],
                        card_nome=purchase["card_nome"],
                        descricao=purchase["descricao"],
                        valor_parcela=purchase["valor_parcela"],
                        parcela_atual=purchase["parcela_atual"],
                        total_parcelas=purchase["total_parcelas"],
                        ate_data=purchase["ate_data"],
                    )
                    for purchase in sorted(
                        person_data["purchases"].values(),
                        key=lambda x: (x["ate_data"], x["descricao"]),
                        reverse=True,
                    )
                ],
            )
            for person_id, person_data in by_person.items()
        ]
        out.sort(key=lambda x: (x.compras_parceladas, x.pessoa_nome.lower()), reverse=True)
        return out, total_installments_month

    def _card_totals(self, user_id: UUID, period_id: UUID) -> list[CardPeriodTotal]:
        user_cards: list[Card] = self._cards.list_by_user(user_id)
        out: list[CardPeriodTotal] = []
        for c in user_cards:
            t = Decimal(str(self._card_txs.sum_by_card_period(user_id, c.id, period_id)))
            out.append(CardPeriodTotal(card_id=c.id, card_nome=c.nome, total=t))
        out.sort(key=lambda x: x.total, reverse=True)
        return out

    def _usage_by_person_cards(self, user_id: UUID, period_id: UUID) -> list[PersonUsageDashboardRow]:
        txs = self._card_tx_shares.list_transactions_with_shares_for_period(user_id, period_id)
        card_names = {c.id: c.nome for c in self._cards.list_by_user(user_id)}
        person_cards: dict[UUID | None, dict[UUID | None, dict[str, object]]] = {}
        person_fixed: dict[UUID | None, list[PersonFixedExpenseUsageRow]] = {}
        person_names: dict[UUID | None, str] = {}

        def ensure_person(person_id: UUID | None, person_name: str) -> None:
            person_names[person_id] = person_name
            if person_id not in person_cards:
                person_cards[person_id] = {}
            if person_id not in person_fixed:
                person_fixed[person_id] = []

        def add_card_total(
            person_id: UUID | None, person_name: str, card_id: UUID | None, card_name: str, amount: Decimal
        ) -> None:
            ensure_person(person_id, person_name)
            cards = person_cards[person_id]
            current = cards.get(card_id)
            if current is None:
                current = {"card_nome": card_name, "total": Decimal("0"), "lancamentos": []}
                cards[card_id] = current
            current["total"] = current["total"] + amount

        def add_card_transaction(
            person_id: UUID | None,
            person_name: str,
            card_id: UUID | None,
            card_name: str,
            transaction_id: UUID,
            descricao: str,
            tx_date: date,
            amount: Decimal,
            pago: bool,
            installment_number: int,
            installment_total: int,
        ) -> None:
            add_card_total(person_id, person_name, card_id, card_name, amount)
            card_data = person_cards[person_id][card_id]
            lancamentos: list[PersonCardUsageRow.TransactionRow] = card_data["lancamentos"]  # type: ignore[assignment]
            lancamentos.append(
                PersonCardUsageRow.TransactionRow(
                    transaction_id=transaction_id,
                    descricao=descricao,
                    data=tx_date,
                    valor=amount,
                    pago=pago,
                    falta_pagar=Decimal("0.00") if pago else amount,
                    parcela_atual=installment_number,
                    parcela_total=installment_total,
                )
            )

        for tx in txs:
            card_name = card_names.get(tx.card_id, "Cartao removido")
            if tx.shares:
                for sh in tx.shares:
                    spender_name = sh.spender.nome if sh.spender else "Pessoa removida"
                    share_pago = bool(getattr(sh, "pago", False))
                    add_card_transaction(
                        sh.spender_id,
                        spender_name,
                        tx.card_id,
                        card_name,
                        tx.id,
                        tx.descricao,
                        tx.data,
                        sh.valor,
                        share_pago,
                        tx.installment_number,
                        tx.installment_total,
                    )
                continue
            add_card_transaction(
                None,
                "Sem pessoa",
                tx.card_id,
                card_name,
                tx.id,
                tx.descricao,
                tx.data,
                tx.valor,
                tx.pago,
                tx.installment_number,
                tx.installment_total,
            )

        fixed_expenses = self._expenses.list_fixed_by_period(user_id, period_id)
        for expense in fixed_expenses:
            if expense.shares:
                for sh in expense.shares:
                    spender_name = sh.spender.nome if sh.spender else "Pessoa removida"
                    ensure_person(sh.spender_id, spender_name)
                    person_fixed[sh.spender_id].append(
                        PersonFixedExpenseUsageRow(
                            expense_id=expense.id,
                            descricao=expense.descricao,
                            total=sh.valor,
                            pago=bool(getattr(sh, "pago", False)),
                            falta_pagar=(
                                Decimal("0.00")
                                if bool(getattr(sh, "pago", False))
                                else sh.valor
                            ),
                        )
                    )
                continue
            ensure_person(None, "Sem pessoa")
            person_fixed[None].append(
                PersonFixedExpenseUsageRow(
                    expense_id=expense.id,
                    descricao=expense.descricao,
                    total=expense.valor,
                    pago=expense.pago,
                    falta_pagar=Decimal("0.00") if expense.pago else expense.valor,
                )
            )

        pending_debts_by_spender: dict[UUID, list[PersonDebtorUsageRow]] = {}
        for loan in self._debtors.list_loans_by_user(user_id):
            if loan.spender_id is None:
                continue
            paid = sum((payment.valor_pago for payment in loan.pagamentos), Decimal("0.00"))
            pending = (loan.valor_emprestado - paid).quantize(Decimal("0.01"))
            latest_payment = max((payment.data_pagamento for payment in loan.pagamentos), default=None)
            base_date = latest_payment or loan.data_emprestimo
            days_without_payment = max(0, (date.today() - base_date).days) if base_date else None
            is_paid = pending <= Decimal("0.00")
            falta_pagar = pending if pending > Decimal("0.00") else Decimal("0.00")
            pending_debts_by_spender.setdefault(loan.spender_id, []).append(
                PersonDebtorUsageRow(
                    loan_id=loan.id,
                    spender_id=loan.spender_id,
                    devedor_nome=loan.devedor_nome,
                    valor_emprestado=loan.valor_emprestado,
                    valor_pago=paid,
                    valor_restante=pending,
                    pago=is_paid,
                    falta_pagar=falta_pagar,
                    data_emprestimo=loan.data_emprestimo,
                    ultimo_pagamento_em=latest_payment,
                    dias_sem_pagamento=days_without_payment,
                )
            )
            spender_name = loan.spender.nome if loan.spender is not None else loan.devedor_nome
            ensure_person(loan.spender_id, spender_name)

        rows: list[PersonUsageDashboardRow] = []
        for person_id, cards_data in person_cards.items():
            pessoa_nome = person_names.get(person_id, "Sem pessoa")
            card_rows: list[PersonCardUsageRow] = []
            for card_id, card_data in cards_data.items():
                lancamentos: list[PersonCardUsageRow.TransactionRow] = card_data["lancamentos"]  # type: ignore[assignment]
                lancamentos.sort(key=lambda x: (x.data, x.descricao.lower()), reverse=True)
                card_rows.append(
                    PersonCardUsageRow(
                        card_id=card_id,
                        card_nome=card_data["card_nome"],
                        total=card_data["total"],
                        lancamentos=lancamentos,
                    )
                )
            card_rows.sort(key=lambda x: x.total, reverse=True)
            total_cards = sum((row.total for row in card_rows), Decimal("0"))
            total_cards_pending = sum(
                (tx.falta_pagar for row in card_rows for tx in row.lancamentos),
                Decimal("0.00"),
            )
            fixed_rows = sorted(
                person_fixed.get(person_id, []),
                key=lambda x: x.total,
                reverse=True,
            )
            total_fixed = sum((row.total for row in fixed_rows), Decimal("0.00"))
            total_fixed_pending = sum((row.falta_pagar for row in fixed_rows), Decimal("0.00"))
            debtor_rows = pending_debts_by_spender.get(person_id, []) if person_id is not None else []
            pending_debt = sum((row.falta_pagar for row in debtor_rows), Decimal("0.00"))
            total_pending = total_cards_pending + total_fixed_pending + pending_debt
            rows.append(
                PersonUsageDashboardRow(
                    pessoa_id=person_id,
                    pessoa_nome=pessoa_nome,
                    total_cartoes=total_cards,
                    total_cartoes_falta_pagar=total_cards_pending,
                    total_gastos_fixos=total_fixed,
                    total_gastos_fixos_falta_pagar=total_fixed_pending,
                    total_divida_devedores=pending_debt,
                    total_divida_devedores_falta_pagar=pending_debt,
                    total_geral=total_cards + total_fixed + pending_debt,
                    total_falta_pagar=total_pending,
                    cartoes=card_rows,
                    gastos_fixos=fixed_rows,
                    devedores=debtor_rows,
                )
            )

        rows.sort(key=lambda x: (x.total_geral, x.pessoa_nome.lower()), reverse=True)
        return rows

    def _fixed_expense_lines(self, user_id: UUID, period_id: UUID) -> list[FixedExpensePeriodLine]:
        rows = self._expenses.list_fixed_by_period(user_id, period_id)
        out: list[FixedExpensePeriodLine] = []
        for e in rows:
            if e.categoria is None:
                continue
            out.append(
                FixedExpensePeriodLine(
                    expense_id=e.id,
                    descricao=e.descricao,
                    data=e.data,
                    categoria_id=e.categoria_id,
                    categoria_nome=e.categoria.nome,
                    valor=e.valor,
                )
            )
        return out

    def summary(self, user_id: UUID, period_id: UUID) -> DashboardSummary:
        self._ensure_period(user_id, period_id)

        total_income, total_expenses, monthly_balance = self._monthly_balance(user_id, period_id)
        pending = self._fixed_expense_sum_for_me(user_id, period_id, unpaid_only=True) + self._card_sum_for_me(
            user_id, period_id, unpaid_only=True
        )

        expenses_by_category = self._expenses_by_category(user_id, period_id)
        expenses_by_person = self._expenses_by_person(user_id, period_id)
        expenses_by_person_category = self._expenses_by_person_category(user_id, period_id)
        usage_by_person_cards = self._usage_by_person_cards(user_id, period_id)
        person_installments, total_installments_month = self._person_installments(user_id, period_id)
        goal_progress, goals_total_saved = self._goal_progress(user_id)
        card_totals = self._card_totals(user_id, period_id)
        fixed_expense_lines = self._fixed_expense_lines(user_id, period_id)

        patrimonio_total = monthly_balance + goals_total_saved

        return DashboardSummary(
            period_id=period_id,
            total_income=total_income,
            total_expenses=total_expenses,
            monthly_balance=monthly_balance,
            pending_expenses=pending,
            expenses_by_category=expenses_by_category,
            expenses_by_person=expenses_by_person,
            expenses_by_person_category=expenses_by_person_category,
            usage_by_person_cards=usage_by_person_cards,
            total_installments_month=total_installments_month,
            person_installments=person_installments,
            goal_progress=goal_progress,
            card_totals=card_totals,
            fixed_expense_lines=fixed_expense_lines,
            goals_total_saved=goals_total_saved,
            patrimonio_total=patrimonio_total,
        )

    def summary_cached(self, user_id: UUID, period_id: UUID) -> DashboardSummary:
        """Resumo com cache curto e granular para aliviar recomputações frequentes no frontend."""
        cached_summary = DashboardCache.get_summary(user_id, period_id)
        if cached_summary is not None:
            return cached_summary

        self._ensure_period(user_id, period_id)
        total_income, total_expenses, monthly_balance = self._cached_block(
            "monthly_balance",
            user_id,
            period_id,
            lambda: self._monthly_balance(user_id, period_id),
        )
        pending = self._cached_block(
            "pending_expenses",
            user_id,
            period_id,
            lambda: self._fixed_expense_sum_for_me(user_id, period_id, unpaid_only=True)
            + self._card_sum_for_me(user_id, period_id, unpaid_only=True),
        )
        expenses_by_category = self._cached_block(
            "expenses_by_category",
            user_id,
            period_id,
            lambda: self._expenses_by_category(user_id, period_id),
        )
        expenses_by_person = self._cached_block(
            "expenses_by_person",
            user_id,
            period_id,
            lambda: self._expenses_by_person(user_id, period_id),
        )
        expenses_by_person_category = self._cached_block(
            "expenses_by_person_category",
            user_id,
            period_id,
            lambda: self._expenses_by_person_category(user_id, period_id),
        )
        usage_by_person_cards = self._cached_block(
            "usage_by_person_cards",
            user_id,
            period_id,
            lambda: self._usage_by_person_cards(user_id, period_id),
        )
        person_installments, total_installments_month = self._cached_block(
            "person_installments",
            user_id,
            period_id,
            lambda: self._person_installments(user_id, period_id),
        )
        goal_progress, goals_total_saved = self._cached_block(
            "goal_progress",
            user_id,
            None,
            lambda: self._goal_progress(user_id),
        )
        card_totals = self._cached_block(
            "card_totals",
            user_id,
            period_id,
            lambda: self._card_totals(user_id, period_id),
        )
        fixed_expense_lines = self._cached_block(
            "fixed_expense_lines",
            user_id,
            period_id,
            lambda: self._fixed_expense_lines(user_id, period_id),
        )
        patrimonio_total = monthly_balance + goals_total_saved
        fresh = DashboardSummary(
            period_id=period_id,
            total_income=total_income,
            total_expenses=total_expenses,
            monthly_balance=monthly_balance,
            pending_expenses=pending,
            expenses_by_category=expenses_by_category,
            expenses_by_person=expenses_by_person,
            expenses_by_person_category=expenses_by_person_category,
            usage_by_person_cards=usage_by_person_cards,
            total_installments_month=total_installments_month,
            person_installments=person_installments,
            goal_progress=goal_progress,
            card_totals=card_totals,
            fixed_expense_lines=fixed_expense_lines,
            goals_total_saved=goals_total_saved,
            patrimonio_total=patrimonio_total,
        )
        DashboardCache.set_summary(user_id, period_id, fresh)
        return fresh.model_copy(deep=True)

    def _cached_block(
        self,
        block_name: str,
        user_id: UUID,
        period_id: UUID | None,
        producer: Callable[[], Any],
    ) -> Any:
        cached = DashboardCache.get_block(block_name, user_id, period_id)
        if cached is not None:
            return cached
        value = producer()
        DashboardCache.set_block(block_name, user_id, period_id, value)
        return value
