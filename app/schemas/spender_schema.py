from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SpenderCreate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=200)


class SpenderUpdate(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=200)


class SpenderResponse(BaseModel):
    id: UUID
    nome: str
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
