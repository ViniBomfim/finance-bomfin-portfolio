import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.spender import Spender
    from app.models.trip import Trip


class TripParticipant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trip_participants"
    __table_args__ = (
        UniqueConstraint("trip_id", "spender_id", name="uq_trip_participant"),
    )

    trip_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), index=True
    )
    spender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("spenders.id", ondelete="RESTRICT"), index=True
    )

    trip: Mapped["Trip"] = relationship("Trip", back_populates="participants")
    spender: Mapped["Spender"] = relationship("Spender", back_populates="trip_participants")
