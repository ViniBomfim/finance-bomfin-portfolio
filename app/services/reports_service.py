from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.card_transaction_repository import CardTransactionRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.expense_repository import ExpenseRepository
from app.repositories.income_repository import IncomeRepository
from app.repositories.period_repository import PeriodRepository
from app.schemas.reports_schema import CategoryExpenseReportRow, MonthlyFlowRow
from app.services.budget_service import BudgetService
from app.services.category_spending_merge import merge_expense_and_card_category_rows


class ReportsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._periods = PeriodRepository(db)
        self._incomes = IncomeRepository(db)
        self._expenses = ExpenseRepository(db)
        self._card_txs = CardTransactionRepository(db)
        self._categories = CategoryRepository(db)

    def monthly_flow(self, user_id: UUID, ano: int) -> list[MonthlyFlowRow]:
        all_p = self._periods.list_by_user(user_id)
        year_periods = [p for p in all_p if p.ano == ano]
        year_periods.sort(key=lambda p: p.mes)
        out: list[MonthlyFlowRow] = []
        for p in year_periods:
            rec = Decimal(str(self._incomes.sum_by_period(user_id, p.id)))
            des = Decimal(str(self._expenses.sum_by_period(user_id, p.id))) + Decimal(
                str(self._card_txs.sum_by_period(user_id, p.id))
            )
            out.append(
                MonthlyFlowRow(
                    mes=p.mes,
                    ano=p.ano,
                    period_id=p.id,
                    receitas=rec,
                    despesas=des,
                    saldo=rec - des,
                )
            )
        return out

    def expenses_by_category(self, user_id: UUID, period_id: UUID) -> list[CategoryExpenseReportRow]:
        p = self._periods.get_by_id(period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        exp_rows = self._expenses.aggregates_by_category_period(user_id, period_id)
        card_rows = self._card_txs.aggregates_by_category_period(user_id, period_id)
        merged = merge_expense_and_card_category_rows(exp_rows, card_rows)
        rows: list[CategoryExpenseReportRow] = []
        for cid, nome, total in merged:
            cat = self._categories.get_by_id(cid, user_id)
            cor = cat.cor if cat else "#888888"
            rows.append(
                CategoryExpenseReportRow(
                    categoria_id=cid,
                    categoria_nome=nome,
                    cor=cor,
                    total=total,
                )
            )
        rows.sort(key=lambda r: r.total, reverse=True)
        return rows

    def budget_vs_actual(self, user_id: UUID, period_id: UUID):
        """Reutiliza a mesma lógica do comparativo de orçamento."""
        return BudgetService(self.db).compare(user_id, period_id)
