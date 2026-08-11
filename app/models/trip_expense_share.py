import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.spender import Spender
    from app.models.trip_expense import TripExpense


class TripExpenseShare(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trip_expense_shares"

    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    trip_expense_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("trip_expenses.id", ondelete="CASCADE"), index=True
    )
    spender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("spenders.id", ondelete="RESTRICT"), index=True
    )

    trip_expense: Mapped["TripExpense"] = relationship("TripExpense", back_populates="shares")
    spender: Mapped["Spender"] = relationship("Spender", back_populates="trip_expense_shares")
