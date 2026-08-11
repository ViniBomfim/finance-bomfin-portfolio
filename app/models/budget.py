import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.period import Period


class Budget(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("user_id", "categoria_id", "period_id", name="uq_budget_user_cat_period"),)

    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    categoria_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    period_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("periods.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)

    categoria: Mapped["Category"] = relationship("Category")
    period: Mapped["Period"] = relationship("Period", back_populates="budgets")
