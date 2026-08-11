from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.income import Income
from app.services.dashboard_cache import DashboardCache


class IncomeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, income_id: UUID, user_id: UUID) -> Income | None:
        i = self.db.get(Income, income_id)
        if i is None or i.user_id != user_id:
            return None
        return i

    def list_by_period(self, user_id: UUID, period_id: UUID) -> list[Income]:
        stmt = (
            select(Income)
            .where(Income.user_id == user_id, Income.period_id == period_id)
            .order_by(Income.data)
        )
        return list(self.db.execute(stmt).scalars().all())

    def sum_by_period(self, user_id: UUID, period_id: UUID) -> float:
        stmt = select(func.coalesce(func.sum(Income.valor), 0)).where(
            Income.user_id == user_id,
            Income.period_id == period_id,
        )
        return float(self.db.execute(stmt).scalar() or 0)

    def create(self, income: Income) -> Income:
        self.db.add(income)
        self.db.commit()
        self.db.refresh(income)
        DashboardCache.invalidate_user_period(income.user_id, income.period_id)
        return income

    def create_many(self, incomes: list[Income]) -> list[Income]:
        for i in incomes:
            self.db.add(i)
        self.db.commit()
        for i in incomes:
            self.db.refresh(i)
        for i in incomes:
            DashboardCache.invalidate_user_period(i.user_id, i.period_id)
        return incomes

    def update(self, income: Income) -> Income:
        self.db.commit()
        self.db.refresh(income)
        DashboardCache.invalidate_user_period(income.user_id, income.period_id)
        return income

    def delete(self, income: Income) -> None:
        user_id = income.user_id
        period_id = income.period_id
        self.db.delete(income)
        self.db.commit()
        DashboardCache.invalidate_user_period(user_id, period_id)
