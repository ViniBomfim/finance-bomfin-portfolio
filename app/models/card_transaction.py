import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.card import Card
    from app.models.card_transaction_share import CardTransactionShare
    from app.models.period import Period
    from app.models.category import Category


class CardTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "card_transactions"

    descricao: Mapped[str] = mapped_column(String(500), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    pago: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    from_statement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    installment_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    installment_total: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Liga todas as parcelas da MESMA compra. Permite agrupar/excluir/editar sem heurística frágil.
    installment_group_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    card_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("cards.id", ondelete="CASCADE"), index=True)
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    period_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("periods.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)

    card: Mapped["Card"] = relationship("Card", back_populates="transactions")
    period: Mapped["Period"] = relationship("Period", back_populates="card_transactions")
    categoria: Mapped["Category | None"] = relationship("Category")
    shares: Mapped[list["CardTransactionShare"]] = relationship(
        "CardTransactionShare",
        back_populates="card_transaction",
        cascade="all, delete-orphan",
    )
