from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class GoalPoolSummaryResponse(BaseModel):
    period_id: UUID = Field(..., description="Competência a que os totais se referem")
    pool_total: Decimal = Field(
        ..., description="Despesas fixas em categorias Metas lançadas no mês"
    )
    deposited_total: Decimal = Field(
        ..., description="Depósitos menos retiradas registrados no mês"
    )
    available: Decimal = Field(
        ...,
        description="Saldo livre para dividir no mês (pool - depósitos + retiradas - receitas de retirada)",
    )

class GoalCreate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=200)
    tipo: str = Field(..., pattern="^(short|medium|long)$")
    valor_meta: Decimal = Field(..., gt=0)
    valor_atual: Decimal = Field(default=Decimal("0"), ge=0)
    data_inicio: date
    data_fim: date | None = None
    status: str = Field(default="active", max_length=40)


class GoalUpdate(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=200)
    tipo: str | None = Field(None, pattern="^(short|medium|long)$")
    valor_meta: Decimal | None = Field(None, gt=0)
    data_fim: date | None = None
    status: str | None = Field(None, max_length=40)


class GoalResponse(BaseModel):
    id: UUID
    nome: str
    tipo: str
    valor_meta: Decimal
    valor_atual: Decimal
    data_inicio: date
    data_fim: date | None
    status: str
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GoalProgressResponse(BaseModel):
    goal_id: UUID
    tipo: str
    valor_meta: Decimal
    valor_atual: Decimal
    progress_percent: float


class GoalTransactionCreate(BaseModel):
    tipo: str = Field(..., pattern="^(deposit|withdraw)$")
    valor: Decimal = Field(..., gt=0)
    descricao: str | None = None
    data: date
    launch_as_income: bool = False
    categoria_id: UUID | None = None

    @model_validator(mode="after")
    def validate_income_launch(self) -> "GoalTransactionCreate":
        if self.launch_as_income:
            if self.tipo != "withdraw":
                raise ValueError("launch_as_income só é permitido em retiradas")
            if self.categoria_id is None:
                raise ValueError("categoria_id é obrigatório ao lançar como receita")
        return self


class GoalTransactionResponse(BaseModel):
    id: UUID
    tipo: str
    valor: Decimal
    descricao: str | None
    data: date
    goal_id: UUID
    user_id: UUID
    income_id: UUID | None = None
    period_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
