from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base

INACTIVITY_LOGOUT_MINUTES_KEY = "inactivity_logout_minutes"
INACTIVITY_LOGOUT_ENABLED_KEY = "inactivity_logout_enabled"
DEFAULT_INACTIVITY_LOGOUT_MINUTES = 60
DEFAULT_INACTIVITY_LOGOUT_ENABLED = True
MIN_INACTIVITY_LOGOUT_MINUTES = 1
MAX_INACTIVITY_LOGOUT_MINUTES = 24 * 60 * 7  # 7 dias


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
