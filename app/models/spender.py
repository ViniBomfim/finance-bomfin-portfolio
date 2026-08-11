import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.card_transaction_share import CardTransactionShare
    from app.models.expense_share import ExpenseShare
    from app.models.trip_expense import TripExpense
    from app.models.trip_expense_share import TripExpenseShare
    from app.models.trip_participant import TripParticipant


class Spender(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "spenders"

    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    is_global: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="spenders",
        foreign_keys=[user_id],
    )
    shares: Mapped[list["CardTransactionShare"]] = relationship(
        "CardTransactionShare", back_populates="spender"
    )
    expense_shares: Mapped[list["ExpenseShare"]] = relationship(
        "ExpenseShare", back_populates="spender"
    )
    trip_participants: Mapped[list["TripParticipant"]] = relationship(
        "TripParticipant", back_populates="spender"
    )
    trip_paid_expenses: Mapped[list["TripExpense"]] = relationship(
        "TripExpense",
        back_populates="paid_by",
        foreign_keys="TripExpense.paid_by_spender_id",
    )
    trip_expense_shares: Mapped[list["TripExpenseShare"]] = relationship(
        "TripExpenseShare", back_populates="spender"
    )
