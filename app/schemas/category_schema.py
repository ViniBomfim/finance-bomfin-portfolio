from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=120)
    cor: str | None = Field(default=None, max_length=32)
    tipo: str = Field(..., pattern="^(income|expense)$")


class CategoryUpdate(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=120)
    cor: str | None = Field(None, max_length=32)
    tipo: str | None = Field(None, pattern="^(income|expense)$")


class CategoryResponse(BaseModel):
    id: UUID
    nome: str
    cor: str
    tipo: str
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
