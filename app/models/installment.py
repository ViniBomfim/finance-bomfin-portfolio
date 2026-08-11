import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.expense import Expense
    from app.models.period import Period


class Installment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "installments"

    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    pago: Mapped[bool] = mapped_column(default=False, nullable=False)
    expense_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), index=True)
    period_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("periods.id", ondelete="CASCADE"), index=True)

    expense: Mapped["Expense"] = relationship("Expense", back_populates="installments")
    period: Mapped["Period"] = relationship("Period", back_populates="installments")
