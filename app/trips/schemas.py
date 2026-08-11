from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.trips.enums import PaymentMethod, TripCategory, TripStatus


class TripParticipantInput(BaseModel):
    spender_id: UUID | None = None
    nome: str | None = Field(None, min_length=1, max_length=200)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_input(self) -> "TripParticipantInput":
        has_id = self.spender_id is not None
        has_name = bool(self.nome and self.nome.strip())
        if has_id == has_name:
            raise ValueError("Informe spender_id (global) ou nome (local da viagem).")
        return self


class TripParticipantResponse(BaseModel):
    spender_id: UUID
    spender_nome: str

    model_config = ConfigDict(from_attributes=True)


class TripCreate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=200)
    destino: str | None = Field(None, max_length=200)
    data_inicio: date | None = None
    data_fim: date | None = None
    moeda_base: str = Field("BRL", min_length=2, max_length=8)
    orcamento_total: Decimal | None = Field(None, ge=0)
    status: TripStatus = TripStatus.PLANNING
    observacoes: str | None = Field(None, max_length=4000)
    participant_spender_ids: list[UUID] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class TripUpdate(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=200)
    destino: str | None = Field(None, max_length=200)
    data_inicio: date | None = None
    data_fim: date | None = None
    moeda_base: str | None = Field(None, min_length=2, max_length=8)
    orcamento_total: Decimal | None = Field(None, ge=0)
    status: TripStatus | None = None
    observacoes: str | None = Field(None, max_length=4000)

    model_config = ConfigDict(extra="forbid")


class TripCategoryTotal(BaseModel):
    categoria: TripCategory
    total: Decimal


class TripPersonTotal(BaseModel):
    spender_id: UUID
    spender_nome: str
    total_pago: Decimal
    total_consumido: Decimal
    saldo: Decimal


class TripPersonCategoryLine(BaseModel):
    categoria: TripCategory
    total: Decimal


class TripPersonConsumptionBreakdown(BaseModel):
    spender_id: UUID
    spender_nome: str
    total: Decimal
    por_categoria: list[TripPersonCategoryLine] = Field(default_factory=list)


class TripResponse(BaseModel):
    id: UUID
    nome: str
    destino: str | None
    data_inicio: date | None
    data_fim: date | None
    moeda_base: str
    orcamento_total: Decimal | None
    status: TripStatus
    observacoes: str | None
    user_id: UUID
    participants: list[TripParticipantResponse] = Field(default_factory=list)
    total_gasto: Decimal = Decimal("0")
    total_por_categoria: list[TripCategoryTotal] = Field(default_factory=list)
    total_por_pessoa: list[TripPersonTotal] = Field(default_factory=list)
    consumo_por_pessoa: list[TripPersonConsumptionBreakdown] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TripExpenseShareInput(BaseModel):
    spender_id: UUID
    valor: Decimal = Field(..., gt=0)

    model_config = ConfigDict(extra="forbid")


class TripExpenseShareResponse(BaseModel):
    spender_id: UUID
    spender_nome: str
    valor: Decimal


class TripExpenseCreate(BaseModel):
    descricao: str = Field(..., min_length=1, max_length=500)
    valor: Decimal = Field(..., gt=0)
    moeda: str = Field("BRL", min_length=2, max_length=8)
    taxa_cambio: Decimal | None = Field(None, gt=0)
    data: date
    categoria: TripCategory
    forma_pagamento: PaymentMethod = PaymentMethod.CASH
    paid_by_spender_id: UUID
    observacao: str | None = Field(None, max_length=2000)
    shares: list[TripExpenseShareInput] | None = None

    model_config = ConfigDict(extra="forbid")


class TripExpenseUpdate(BaseModel):
    descricao: str | None = Field(None, min_length=1, max_length=500)
    valor: Decimal | None = Field(None, gt=0)
    moeda: str | None = Field(None, min_length=2, max_length=8)
    taxa_cambio: Decimal | None = Field(None, gt=0)
    data: date | None = None
    categoria: TripCategory | None = None
    forma_pagamento: PaymentMethod | None = None
    paid_by_spender_id: UUID | None = None
    observacao: str | None = Field(None, max_length=2000)
    shares: list[TripExpenseShareInput] | None = None

    model_config = ConfigDict(extra="forbid")


class TripExpenseResponse(BaseModel):
    id: UUID
    trip_id: UUID
    user_id: UUID
    descricao: str
    valor: Decimal
    moeda: str
    taxa_cambio: Decimal | None
    valor_base: Decimal
    data: date
    categoria: TripCategory
    forma_pagamento: PaymentMethod
    paid_by_spender_id: UUID
    paid_by_nome: str
    observacao: str | None
    pushed_expense_id: UUID | None
    shares: list[TripExpenseShareResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TripSettlementTransfer(BaseModel):
    from_spender_id: UUID
    from_spender_nome: str
    to_spender_id: UUID
    to_spender_nome: str
    valor: Decimal


class TripSettlementResponse(BaseModel):
    trip_id: UUID
    moeda_base: str
    saldos: list[TripPersonTotal]
    transferencias: list[TripSettlementTransfer]


class PushToMonthRequest(BaseModel):
    period_id: UUID
    pago: bool = False

    model_config = ConfigDict(extra="forbid")
