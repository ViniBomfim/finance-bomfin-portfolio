import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.goal import Goal


class GoalTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "goal_transactions"

    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # deposit | withdraw
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    goal_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    income_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incomes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    period_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("periods.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    goal: Mapped["Goal"] = relationship("Goal", back_populates="transactions")
