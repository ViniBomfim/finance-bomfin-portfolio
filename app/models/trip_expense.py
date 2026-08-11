import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.trips.enums import PaymentMethod, TripCategory

if TYPE_CHECKING:
    from app.expenses.model import Expense
    from app.models.spender import Spender
    from app.models.trip import Trip
    from app.models.trip_expense_share import TripExpenseShare


_trip_category_enum = SAEnum(
    TripCategory,
    name="trip_category",
    native_enum=False,
    values_callable=lambda x: [m.value for m in x],
    length=20,
)

_payment_method_enum = SAEnum(
    PaymentMethod,
    name="trip_payment_method",
    native_enum=False,
    values_callable=lambda x: [m.value for m in x],
    length=20,
)


class TripExpense(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Gasto lançado dentro de uma viagem."""

    __tablename__ = "trip_expenses"

    descricao: Mapped[str] = mapped_column(String(500), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    moeda: Mapped[str] = mapped_column(String(8), nullable=False, default="BRL")
    taxa_cambio: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    valor_base: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    categoria: Mapped[TripCategory] = mapped_column(_trip_category_enum, nullable=False)
    forma_pagamento: Mapped[PaymentMethod] = mapped_column(
        _payment_method_enum, nullable=False, default=PaymentMethod.CASH
    )
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)

    trip_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    paid_by_spender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("spenders.id", ondelete="RESTRICT"), index=True
    )
    pushed_expense_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("expenses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    trip: Mapped["Trip"] = relationship("Trip", back_populates="expenses")
    paid_by: Mapped["Spender"] = relationship(
        "Spender",
        foreign_keys=[paid_by_spender_id],
        back_populates="trip_paid_expenses",
    )
    pushed_expense: Mapped["Expense | None"] = relationship(
        "Expense",
        foreign_keys=[pushed_expense_id],
    )
    shares: Mapped[list["TripExpenseShare"]] = relationship(
        "TripExpenseShare",
        back_populates="trip_expense",
        cascade="all, delete-orphan",
    )
