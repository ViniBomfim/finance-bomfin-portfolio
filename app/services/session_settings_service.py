from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.platform_setting import (
    DEFAULT_INACTIVITY_LOGOUT_ENABLED,
    DEFAULT_INACTIVITY_LOGOUT_MINUTES,
    INACTIVITY_LOGOUT_ENABLED_KEY,
    INACTIVITY_LOGOUT_MINUTES_KEY,
    MAX_INACTIVITY_LOGOUT_MINUTES,
    MIN_INACTIVITY_LOGOUT_MINUTES,
)
from app.repositories.platform_setting_repository import PlatformSettingRepository


class SessionSettingsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = PlatformSettingRepository(db)

    def get_inactivity_logout_minutes(self) -> int:
        row = self.settings.get(INACTIVITY_LOGOUT_MINUTES_KEY)
        if row is None:
            return DEFAULT_INACTIVITY_LOGOUT_MINUTES
        try:
            value = int(row.value.strip())
        except ValueError:
            return DEFAULT_INACTIVITY_LOGOUT_MINUTES
        if value < MIN_INACTIVITY_LOGOUT_MINUTES or value > MAX_INACTIVITY_LOGOUT_MINUTES:
            return DEFAULT_INACTIVITY_LOGOUT_MINUTES
        return value

    def is_inactivity_logout_enabled(self) -> bool:
        row = self.settings.get(INACTIVITY_LOGOUT_ENABLED_KEY)
        if row is None:
            return DEFAULT_INACTIVITY_LOGOUT_ENABLED
        return row.value.strip().lower() in {"1", "true", "yes", "on"}

    def get_session_settings(self) -> dict[str, int | bool]:
        return {
            "inactivity_logout_minutes": self.get_inactivity_logout_minutes(),
            "inactivity_logout_enabled": self.is_inactivity_logout_enabled(),
        }

    def set_inactivity_logout_minutes(self, minutes: int) -> int:
        if minutes < MIN_INACTIVITY_LOGOUT_MINUTES or minutes > MAX_INACTIVITY_LOGOUT_MINUTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Tempo deve estar entre {MIN_INACTIVITY_LOGOUT_MINUTES} e "
                    f"{MAX_INACTIVITY_LOGOUT_MINUTES} minutos."
                ),
            )
        self.settings.set(INACTIVITY_LOGOUT_MINUTES_KEY, str(minutes))
        return minutes

    def set_inactivity_logout_enabled(self, enabled: bool) -> bool:
        self.settings.set(INACTIVITY_LOGOUT_ENABLED_KEY, "1" if enabled else "0")
        return enabled

    def update_session_settings(
        self,
        *,
        minutes: int | None = None,
        enabled: bool | None = None,
    ) -> dict[str, int | bool]:
        if minutes is None and enabled is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Informe ao menos um campo para atualizar.",
            )
        if minutes is not None:
            self.set_inactivity_logout_minutes(minutes)
        if enabled is not None:
            self.set_inactivity_logout_enabled(enabled)
        return self.get_session_settings()
