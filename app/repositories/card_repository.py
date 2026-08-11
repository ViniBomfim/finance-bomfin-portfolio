from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.card import Card
from app.services.dashboard_cache import DashboardCache


class CardRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, card_id: UUID, user_id: UUID) -> Card | None:
        c = self.db.get(Card, card_id)
        if c is None or c.user_id != user_id:
            return None
        return c

    def list_by_user(self, user_id: UUID) -> list[Card]:
        stmt = select(Card).where(Card.user_id == user_id).order_by(Card.nome)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, card: Card) -> Card:
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)
        DashboardCache.invalidate_user(card.user_id)
        return card

    def update(self, card: Card) -> Card:
        self.db.commit()
        self.db.refresh(card)
        DashboardCache.invalidate_user(card.user_id)
        return card

    def delete(self, card: Card) -> None:
        user_id = card.user_id
        self.db.delete(card)
        self.db.commit()
        DashboardCache.invalidate_user(user_id)
