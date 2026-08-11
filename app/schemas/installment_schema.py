from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class InstallmentResponse(BaseModel):
    id: UUID
    numero: int
    total: int
    valor: Decimal
    pago: bool
    expense_id: UUID
    period_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
