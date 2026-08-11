from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.expenses.enums import ExpenseType, RecurrenceValueMode


class ExpenseShareInput(BaseModel):
    spender_id: UUID
    valor: Decimal = Field(..., ne=0)
    pago: bool = False


class ExpenseShareResponse(BaseModel):
    spender_id: UUID
    spender_nome: str
    valor: Decimal
    pago: bool = False


class ExpenseCreate(BaseModel):
    """Payload para criar despesa."""

    descricao: str = Field(..., min_length=1, max_length=500, examples=["Aluguel"])
    valor: Decimal = Field(..., gt=0, examples=["1500.00"])
    data: date
    period_id: UUID
    categoria_id: UUID
    tipo: ExpenseType = Field(..., examples=[ExpenseType.FIXED])
    recorrente: bool = False
    recurrence_value_mode: RecurrenceValueMode = RecurrenceValueMode.SAME_VALUE
    pago: bool = False
    shares: list[ExpenseShareInput] | None = None

    model_config = ConfigDict(extra="forbid")


class ExpenseUpdate(BaseModel):
    """Atualização parcial de despesa."""

    descricao: str | None = Field(None, min_length=1, max_length=500)
    valor: Decimal | None = Field(None, gt=0)
    data: date | None = None
    period_id: UUID | None = None
    categoria_id: UUID | None = None
    tipo: ExpenseType | None = None
    recorrente: bool | None = None
    recurrence_value_mode: RecurrenceValueMode | None = None
    pago: bool | None = None
    shares: list[ExpenseShareInput] | None = None

    model_config = ConfigDict(extra="forbid")


class ExpenseResponse(BaseModel):
    """Despesa persistida."""

    id: UUID
    descricao: str
    valor: Decimal
    data: date
    tipo: ExpenseType
    recorrente: bool
    pago: bool
    period_id: UUID
    categoria_id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    shares: list[ExpenseShareResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class GenerateInstallmentsRequest(BaseModel):
    """Gera N parcelas a partir do valor total da despesa."""

    total_parcelas: int = Field(..., ge=2, le=120)
    start_period_id: UUID

    model_config = ConfigDict(extra="forbid")


class ExpenseListFilter(BaseModel):
    """Filtro de listagem (validação de presença de filtros no `deps`)."""

    period_id: UUID | None = Field(default=None, description="Listar despesas do período")
    categoria_id: UUID | None = Field(default=None, description="Listar despesas da categoria")

    model_config = ConfigDict(extra="forbid")


