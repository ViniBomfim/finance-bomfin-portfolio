import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import JSON

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CardSplitTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Proporções de divisão por descrição (canônica) e cartão — reaplicadas na importação."""

    __tablename__ = "card_split_templates"
    __table_args__ = (
        UniqueConstraint("user_id", "card_id", "description_key", name="uq_card_split_tpl_desc"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    card_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cards.id", ondelete="CASCADE"), index=True
    )
    description_key: Mapped[str] = mapped_column(String(500), nullable=False)
    # [{"spender_id": "<uuid>", "ratio": "0.5"}, ...] — ratios somam 1
    parts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
