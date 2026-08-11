from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class BudgetCreate(BaseModel):
    categoria_id: UUID
    period_id: UUID
    valor: Decimal = Field(..., ge=0)


class BudgetUpdate(BaseModel):
    valor: Decimal | None = Field(None, ge=0)


class BudgetResponse(BaseModel):
    id: UUID
    categoria_id: UUID
    period_id: UUID
    valor: Decimal
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BudgetCompareRow(BaseModel):
    categoria_id: UUID
    categoria_nome: str
    planejado: Decimal
    realizado: Decimal
    diferenca: Decimal


class ReplicateYearBudgetsRequest(BaseModel):
    """Replica orçamentos mês a mês de um ano para outro (ex.: estrutura 2026 → 2027)."""

    from_ano: int = Field(..., ge=2000, le=2100)
    to_ano: int = Field(..., ge=2000, le=2100)
