from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.card import Card
from app.repositories.card_repository import CardRepository
from app.schemas.card_schema import CardCreate, CardUpdate


class CardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.cards = CardRepository(db)

    def create(self, user_id: UUID, data: CardCreate) -> Card:
        c = Card(
            nome=data.nome,
            banco=data.banco,
            limite=data.limite,
            fechamento=data.fechamento,
            vencimento=data.vencimento,
            user_id=user_id,
        )
        return self.cards.create(c)

    def update(self, user_id: UUID, card_id: UUID, data: CardUpdate) -> Card:
        c = self.cards.get_by_id(card_id, user_id)
        if c is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
        if data.nome is not None:
            c.nome = data.nome
        if data.banco is not None:
            c.banco = data.banco
        if data.limite is not None:
            c.limite = data.limite
        if data.fechamento is not None:
            c.fechamento = data.fechamento
        if data.vencimento is not None:
            c.vencimento = data.vencimento
        return self.cards.update(c)

    def delete(self, user_id: UUID, card_id: UUID) -> None:
        c = self.cards.get_by_id(card_id, user_id)
        if c is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
        self.cards.delete(c)

    def list_cards(self, user_id: UUID) -> list[Card]:
        return self.cards.list_by_user(user_id)

    def get(self, user_id: UUID, card_id: UUID) -> Card:
        c = self.cards.get_by_id(card_id, user_id)
        if c is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
        return c
