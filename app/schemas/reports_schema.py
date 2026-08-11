from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class MonthlyFlowRow(BaseModel):
    mes: int
    ano: int
    period_id: UUID
    receitas: Decimal
    despesas: Decimal
    saldo: Decimal


class CategoryExpenseReportRow(BaseModel):
    categoria_id: UUID
    categoria_nome: str
    cor: str
    total: Decimal
