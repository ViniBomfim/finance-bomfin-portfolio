from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.card_split_template import CardSplitTemplate


class CardSplitTemplateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_key(self, user_id: UUID, card_id: UUID, description_key: str) -> CardSplitTemplate | None:
        stmt = select(CardSplitTemplate).where(
            CardSplitTemplate.user_id == user_id,
            CardSplitTemplate.card_id == card_id,
            CardSplitTemplate.description_key == description_key,
        )
        return self.db.execute(stmt).scalars().first()

    def upsert(self, row: CardSplitTemplate, *, commit: bool = True) -> CardSplitTemplate:
        existing = self.get_by_key(row.user_id, row.card_id, row.description_key)
        if existing is not None:
            existing.parts = row.parts
            if commit:
                self.db.commit()
                self.db.refresh(existing)
            else:
                self.db.flush()
            return existing
        self.db.add(row)
        if commit:
            self.db.commit()
            self.db.refresh(row)
        else:
            self.db.flush()
        return row

    def delete_by_key(self, user_id: UUID, card_id: UUID, description_key: str) -> int:
        stmt = delete(CardSplitTemplate).where(
            CardSplitTemplate.user_id == user_id,
            CardSplitTemplate.card_id == card_id,
            CardSplitTemplate.description_key == description_key,
        )
        r = self.db.execute(stmt)
        self.db.commit()
        return int(r.rowcount or 0)
