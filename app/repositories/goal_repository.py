from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.services.dashboard_cache import DashboardCache


class GoalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, goal_id: UUID, user_id: UUID) -> Goal | None:
        g = self.db.get(Goal, goal_id)
        if g is None or g.user_id != user_id:
            return None
        return g

    def list_by_user(self, user_id: UUID) -> list[Goal]:
        stmt = select(Goal).where(Goal.user_id == user_id).order_by(Goal.data_inicio.desc())
        return list(self.db.execute(stmt).scalars().all())

    def sum_valor_atual(self, user_id: UUID) -> float:
        stmt = select(func.coalesce(func.sum(Goal.valor_atual), 0)).where(Goal.user_id == user_id)
        return float(self.db.execute(stmt).scalar() or 0)

    def create(self, goal: Goal) -> Goal:
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        DashboardCache.invalidate_user(goal.user_id)
        return goal

    def update(self, goal: Goal) -> Goal:
        self.db.commit()
        self.db.refresh(goal)
        DashboardCache.invalidate_user(goal.user_id)
        return goal

    def delete(self, goal: Goal) -> None:
        user_id = goal.user_id
        self.db.delete(goal)
        self.db.commit()
        DashboardCache.invalidate_user(user_id)
