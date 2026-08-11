from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.expenses.model import Expense
from app.models.expense_share import ExpenseShare
from app.services.dashboard_cache import DashboardCache


class ExpenseShareRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_expense(self, expense_id: UUID) -> list[ExpenseShare]:
        stmt = (
            select(ExpenseShare)
            .options(selectinload(ExpenseShare.spender))
            .where(ExpenseShare.expense_id == expense_id)
            .order_by(ExpenseShare.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def delete_for_expense(self, expense_id: UUID) -> None:
        expense = self.db.get(Expense, expense_id)
        stmt = delete(ExpenseShare).where(ExpenseShare.expense_id == expense_id)
        self.db.execute(stmt)
        self.db.commit()
        if expense is not None:
            DashboardCache.invalidate_user_period(expense.user_id, expense.period_id)

    def create_many(self, rows: list[ExpenseShare]) -> list[ExpenseShare]:
        expense_by_id: dict[UUID, Expense] = {}
        for row in rows:
            if row.expense_id not in expense_by_id:
                expense = self.db.get(Expense, row.expense_id)
                if expense is not None:
                    expense_by_id[row.expense_id] = expense
        for r in rows:
            self.db.add(r)
        self.db.commit()
        for r in rows:
            self.db.refresh(r)
        for expense in expense_by_id.values():
            DashboardCache.invalidate_user_period(expense.user_id, expense.period_id)
        return rows

    def list_expenses_with_shares_for_period(self, user_id: UUID, period_id: UUID) -> list[Expense]:
        stmt = (
            select(Expense)
            .options(
                selectinload(Expense.categoria),
                selectinload(Expense.shares).selectinload(ExpenseShare.spender),
            )
            .where(Expense.user_id == user_id, Expense.period_id == period_id)
            .order_by(Expense.data.asc(), Expense.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_expenses_with_shares_for_category(self, user_id: UUID, categoria_id: UUID) -> list[Expense]:
        stmt = (
            select(Expense)
            .options(
                selectinload(Expense.categoria),
                selectinload(Expense.shares).selectinload(ExpenseShare.spender),
            )
            .where(Expense.user_id == user_id, Expense.categoria_id == categoria_id)
            .order_by(Expense.data.asc(), Expense.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())
