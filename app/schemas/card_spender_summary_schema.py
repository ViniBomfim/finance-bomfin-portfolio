from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class SpenderSummaryLine(BaseModel):
    transaction_id: UUID
    descricao: str
    data: date
    valor_parte: Decimal


class SpenderSummaryGroup(BaseModel):
    spender_id: UUID | None
    spender_nome: str | None
    total: Decimal
    lines: list[SpenderSummaryLine]


class CardSpenderSummaryResponse(BaseModel):
    card_id: UUID
    period_id: UUID
    groups: list[SpenderSummaryGroup]
