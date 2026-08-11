from pydantic import BaseModel, Field, model_validator

from app.models.platform_setting import (
    DEFAULT_INACTIVITY_LOGOUT_ENABLED,
    DEFAULT_INACTIVITY_LOGOUT_MINUTES,
    MAX_INACTIVITY_LOGOUT_MINUTES,
    MIN_INACTIVITY_LOGOUT_MINUTES,
)


class SessionSettingsResponse(BaseModel):
    inactivity_logout_enabled: bool = Field(
        ...,
        description="Se o logout automático por inatividade está ativo.",
    )
    inactivity_logout_minutes: int = Field(
        ...,
        ge=MIN_INACTIVITY_LOGOUT_MINUTES,
        le=MAX_INACTIVITY_LOGOUT_MINUTES,
        description="Minutos sem interação até logout automático.",
    )


class SessionSettingsUpdateRequest(BaseModel):
    inactivity_logout_enabled: bool | None = Field(
        None,
        description="Ativa ou desativa o logout automático por inatividade.",
    )
    inactivity_logout_minutes: int | None = Field(
        None,
        ge=MIN_INACTIVITY_LOGOUT_MINUTES,
        le=MAX_INACTIVITY_LOGOUT_MINUTES,
        description="Minutos sem interação até logout automático.",
    )

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "SessionSettingsUpdateRequest":
        if self.inactivity_logout_enabled is None and self.inactivity_logout_minutes is None:
            raise ValueError("Informe ao menos um campo para atualizar.")
        return self


class SessionSettingsDefaults(BaseModel):
    default_inactivity_logout_enabled: bool = DEFAULT_INACTIVITY_LOGOUT_ENABLED
    default_inactivity_logout_minutes: int = DEFAULT_INACTIVITY_LOGOUT_MINUTES
    min_inactivity_logout_minutes: int = MIN_INACTIVITY_LOGOUT_MINUTES
    max_inactivity_logout_minutes: int = MAX_INACTIVITY_LOGOUT_MINUTES
