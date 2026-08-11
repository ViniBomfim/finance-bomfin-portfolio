from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transfer import Transfer


class TransferRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_user(self, user_id: UUID, skip: int = 0, limit: int = 100) -> list[Transfer]:
        stmt = (
            select(Transfer)
            .where(Transfer.user_id == user_id)
            .order_by(Transfer.data.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, transfer: Transfer) -> Transfer:
        self.db.add(transfer)
        self.db.commit()
        self.db.refresh(transfer)
        return transfer
