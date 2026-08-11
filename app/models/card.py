import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.card_transaction import CardTransaction


class Card(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cards"

    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    banco: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    limite: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    fechamento: Mapped[int] = mapped_column(Integer, nullable=False)  # dia do mês
    vencimento: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)

    transactions: Mapped[list["CardTransaction"]] = relationship(
        "CardTransaction", back_populates="card", cascade="all, delete-orphan"
    )
