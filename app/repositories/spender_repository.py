from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.card_transaction_share import CardTransactionShare
from app.models.spender import Spender


class SpenderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_user(self, user_id: UUID, *, only_global: bool = True) -> list[Spender]:
        stmt = select(Spender).where(Spender.user_id == user_id)
        if only_global:
            stmt = stmt.where(Spender.is_global.is_(True))
        stmt = stmt.order_by(Spender.nome.asc())
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id(self, spender_id: UUID, user_id: UUID) -> Spender | None:
        stmt = select(Spender).where(Spender.id == spender_id, Spender.user_id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, s: Spender) -> Spender:
        self.db.add(s)
        self.db.commit()
        self.db.refresh(s)
        return s

    def update(self, s: Spender) -> Spender:
        self.db.commit()
        self.db.refresh(s)
        return s

    def delete(self, s: Spender) -> None:
        self.db.delete(s)
        self.db.commit()

    def count_share_rows(self, spender_id: UUID) -> int:
        stmt = select(func.count()).select_from(CardTransactionShare).where(
            CardTransactionShare.spender_id == spender_id
        )
        return int(self.db.execute(stmt).scalar() or 0)
