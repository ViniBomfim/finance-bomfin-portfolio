import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "ix_notifications_user_tipo_ref_lida",
            "user_id",
            "tipo",
            "referencia_id",
            "lida",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    modulo: Mapped[str] = mapped_column(String(40), nullable=False)
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    severidade: Mapped[str] = mapped_column(String(20), nullable=False)
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    subtitulo: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    lida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    link: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    referencia_id: Mapped[str] = mapped_column(String(64), nullable=False)
    lida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User")
