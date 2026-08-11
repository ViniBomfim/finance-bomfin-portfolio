import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.expenses.model import Expense
    from app.models.spender import Spender


class ExpenseShare(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expense_shares"

    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    pago: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expense_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), index=True
    )
    spender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("spenders.id", ondelete="RESTRICT"), index=True
    )

    expense: Mapped["Expense"] = relationship("Expense", back_populates="shares")
    spender: Mapped["Spender"] = relationship("Spender", back_populates="expense_shares")
