import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.trip_expense import TripExpense
    from app.models.trip_participant import TripParticipant
    from app.models.user import User


class Trip(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Viagem do usuário (área de gastos compartilhados, fora do calendário mensal)."""

    __tablename__ = "trips"

    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    destino: Mapped[str | None] = mapped_column(String(200), nullable=True)
    data_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    moeda_base: Mapped[str] = mapped_column(String(8), nullable=False, default="BRL")
    orcamento_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planning")
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    user: Mapped["User"] = relationship("User", back_populates="trips")
    participants: Mapped[list["TripParticipant"]] = relationship(
        "TripParticipant",
        back_populates="trip",
        cascade="all, delete-orphan",
    )
    expenses: Mapped[list["TripExpense"]] = relationship(
        "TripExpense",
        back_populates="trip",
        cascade="all, delete-orphan",
    )
