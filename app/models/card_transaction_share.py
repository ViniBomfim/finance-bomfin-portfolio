import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.card_transaction import CardTransaction
    from app.models.spender import Spender


class CardTransactionShare(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "card_transaction_shares"

    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    pago: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    card_transaction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("card_transactions.id", ondelete="CASCADE"), index=True
    )
    spender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("spenders.id", ondelete="RESTRICT"), index=True
    )

    card_transaction: Mapped["CardTransaction"] = relationship(
        "CardTransaction", back_populates="shares"
    )
    spender: Mapped["Spender"] = relationship("Spender", back_populates="shares")
