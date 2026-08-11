from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PeriodResponse(BaseModel):
    id: UUID
    mes: int = Field(..., ge=1, le=12)
    ano: int
    status: str
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateYearRequest(BaseModel):
    ano: int = Field(..., ge=2000, le=2100)
