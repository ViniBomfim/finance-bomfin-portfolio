from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class TransferCreate(BaseModel):
    source_type: str = Field(..., max_length=40)
    source_id: UUID | None = None
    destination_type: str = Field(..., max_length=40)
    destination_id: UUID | None = None
    valor: Decimal = Field(..., gt=0)
    data: date


class TransferResponse(BaseModel):
    id: UUID
    source_type: str
    source_id: UUID | None
    destination_type: str
    destination_id: UUID | None
    valor: Decimal
    data: date
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
