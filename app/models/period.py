import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.income import Income
    from app.models.expense import Expense
    from app.models.card_transaction import CardTransaction
    from app.models.installment import Installment
    from app.models.budget import Budget


class Period(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "periods"
    __table_args__ = (UniqueConstraint("user_id", "mes", "ano", name="uq_period_user_month_year"),)

    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")  # open | closed
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)

    user: Mapped["User"] = relationship("User", back_populates="periods")
    incomes: Mapped[list["Income"]] = relationship("Income", back_populates="period", cascade="all, delete-orphan")
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="period", cascade="all, delete-orphan")
    card_transactions: Mapped[list["CardTransaction"]] = relationship(
        "CardTransaction", back_populates="period", cascade="all, delete-orphan"
    )
    installments: Mapped[list["Installment"]] = relationship(
        "Installment", back_populates="period", cascade="all, delete-orphan"
    )
    budgets: Mapped[list["Budget"]] = relationship("Budget", back_populates="period", cascade="all, delete-orphan")

