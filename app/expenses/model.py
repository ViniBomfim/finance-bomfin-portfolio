import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum as SAEnum, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.expenses.enums import ExpenseType

if TYPE_CHECKING:
    from app.models.period import Period
    from app.models.category import Category
    from app.models.installment import Installment
    from app.models.expense_share import ExpenseShare

_expense_type_enum = SAEnum(
    ExpenseType,
    name="expense_type",
    native_enum=False,
    values_callable=lambda x: [m.value for m in x],
    length=20,
)


class Expense(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Despesa do usuário (fixa, variável ou cartão)."""

    __tablename__ = "expenses"

    descricao: Mapped[str] = mapped_column(String(500), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    tipo: Mapped[ExpenseType] = mapped_column(_expense_type_enum, nullable=False)
    recorrente: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pago: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("periods.id", ondelete="CASCADE"), index=True
    )
    categoria_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    period: Mapped["Period"] = relationship("Period", back_populates="expenses")
    categoria: Mapped["Category"] = relationship("Category", back_populates="expenses")
    installments: Mapped[list["Installment"]] = relationship(
        "Installment", back_populates="expense", cascade="all, delete-orphan"
    )
    shares: Mapped[list["ExpenseShare"]] = relationship(
        "ExpenseShare", back_populates="expense", cascade="all, delete-orphan"
    )
