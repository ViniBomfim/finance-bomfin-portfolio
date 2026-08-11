from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

NotificationModulo = Literal["cartoes", "devedores", "metas", "viagens", "gastos_fixos"]
NotificationSeveridade = Literal["urgente", "atencao", "info"]


class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    modulo: NotificationModulo
    tipo: str
    severidade: NotificationSeveridade
    titulo: str
    subtitulo: str
    lida: bool
    link: str
    referencia_id: str
    criado_em: datetime = Field(validation_alias="created_at")
    lida_em: datetime | None = None

    model_config = {"from_attributes": True, "populate_by_name": True}

    @field_serializer("criado_em", "lida_em")
    def _as_utc(self, value: datetime | None) -> datetime | None:
        """SQLite devolve datetimes ingênuos em UTC; sem o fuso o cliente lê como local."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class NotificationGrupos(BaseModel):
    cartoes: list[NotificationResponse] = Field(default_factory=list)
    devedores: list[NotificationResponse] = Field(default_factory=list)
    metas: list[NotificationResponse] = Field(default_factory=list)
    viagens: list[NotificationResponse] = Field(default_factory=list)
    gastos_fixos: list[NotificationResponse] = Field(default_factory=list)


class NotificationListResponse(BaseModel):
    total: int
    grupos: NotificationGrupos


class NotificationMarkAllResponse(BaseModel):
    count: int


class NotificationGenerateResponse(BaseModel):
    created: int
    cleaned: int
    ran: bool = False
