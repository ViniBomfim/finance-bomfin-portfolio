import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.period import Period
    from app.models.category import Category


class Income(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "incomes"

    descricao: Mapped[str] = mapped_column(String(500), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    recorrente: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Marca receitas geradas por retirada de meta: preserva a contabilidade do pool quando a meta é excluída.
    origem_meta: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="0"
    )
    period_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("periods.id", ondelete="CASCADE"), index=True)
    categoria_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)

    period: Mapped["Period"] = relationship("Period", back_populates="incomes")
    categoria: Mapped["Category"] = relationship("Category", back_populates="incomes")
