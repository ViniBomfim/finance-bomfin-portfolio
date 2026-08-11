from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal_transaction import GoalTransaction
from app.services.dashboard_cache import DashboardCache


class GoalTransactionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, tx_id: UUID, user_id: UUID) -> GoalTransaction | None:
        t = self.db.get(GoalTransaction, tx_id)
        if t is None or t.user_id != user_id:
            return None
        return t

    def list_by_goal(self, user_id: UUID, goal_id: UUID) -> list[GoalTransaction]:
        stmt = (
            select(GoalTransaction)
            .where(GoalTransaction.user_id == user_id, GoalTransaction.goal_id == goal_id)
            .order_by(GoalTransaction.data.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, tx: GoalTransaction) -> GoalTransaction:
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(tx)
        DashboardCache.invalidate_user(tx.user_id)
        return tx

    def delete(self, tx: GoalTransaction) -> None:
        user_id = tx.user_id
        self.db.delete(tx)
        self.db.commit()
        DashboardCache.invalidate_user(user_id)
