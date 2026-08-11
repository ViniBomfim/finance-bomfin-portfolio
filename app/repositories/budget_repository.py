from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.budget import Budget


class BudgetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, budget_id: UUID, user_id: UUID) -> Budget | None:
        b = self.db.get(Budget, budget_id)
        if b is None or b.user_id != user_id:
            return None
        return b

    def list_by_period(self, user_id: UUID, period_id: UUID) -> list[Budget]:
        stmt = select(Budget).where(Budget.user_id == user_id, Budget.period_id == period_id)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_category_period(self, user_id: UUID, categoria_id: UUID, period_id: UUID) -> Budget | None:
        stmt = select(Budget).where(
            Budget.user_id == user_id,
            Budget.categoria_id == categoria_id,
            Budget.period_id == period_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, budget: Budget) -> Budget:
        self.db.add(budget)
        self.db.commit()
        self.db.refresh(budget)
        return budget

    def update(self, budget: Budget) -> Budget:
        self.db.commit()
        self.db.refresh(budget)
        return budget

    def delete(self, budget: Budget) -> None:
        self.db.delete(budget)
        self.db.commit()
