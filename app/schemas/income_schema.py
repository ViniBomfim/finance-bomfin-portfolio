from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class IncomeCreate(BaseModel):
    descricao: str = Field(..., min_length=1, max_length=500)
    valor: Decimal = Field(..., gt=0)
    data: date
    period_id: UUID
    categoria_id: UUID
    recorrente: bool = False


class IncomeUpdate(BaseModel):
    descricao: str | None = Field(None, min_length=1, max_length=500)
    valor: Decimal | None = Field(None, gt=0)
    data: date | None = None
    period_id: UUID | None = None
    categoria_id: UUID | None = None
    recorrente: bool | None = None


class IncomeResponse(BaseModel):
    id: UUID
    descricao: str
    valor: Decimal
    data: date
    recorrente: bool
    period_id: UUID
    categoria_id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
