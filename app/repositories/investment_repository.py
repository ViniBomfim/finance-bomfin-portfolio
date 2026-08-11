from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.investment import Investment


class InvestmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, investment_id: UUID, user_id: UUID) -> Investment | None:
        inv = self.db.get(Investment, investment_id)
        if inv is None or inv.user_id != user_id:
            return None
        return inv

    def list_by_user(self, user_id: UUID) -> list[Investment]:
        stmt = select(Investment).where(Investment.user_id == user_id).order_by(Investment.descricao)
        return list(self.db.execute(stmt).scalars().all())

    def sum_valor_atual(self, user_id: UUID) -> float:
        stmt = select(func.coalesce(func.sum(Investment.valor_atual), 0)).where(Investment.user_id == user_id)
        return float(self.db.execute(stmt).scalar() or 0)

    def create(self, row: Investment) -> Investment:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update(self, row: Investment) -> Investment:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: Investment) -> None:
        self.db.delete(row)
        self.db.commit()
