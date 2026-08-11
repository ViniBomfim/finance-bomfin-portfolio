from datetime import date, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CardCreate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=200)
    banco: str = Field(default="", max_length=200)
    limite: Decimal = Field(default=Decimal("0"), ge=0)
    fechamento: int = Field(..., ge=1, le=31)
    vencimento: int = Field(..., ge=1, le=31)


class CardUpdate(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=200)
    banco: str | None = Field(None, max_length=200)
    limite: Decimal | None = Field(None, ge=0)
    fechamento: int | None = Field(None, ge=1, le=31)
    vencimento: int | None = Field(None, ge=1, le=31)


class CardResponse(BaseModel):
    id: UUID
    nome: str
    banco: str
    limite: Decimal
    fechamento: int
    vencimento: int
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CardTransactionShareInput(BaseModel):
    spender_id: UUID
    valor: Decimal = Field(..., ne=0, description="Pode ser negativo se o lançamento for crédito/estorno")
    pago: bool = False


class CardTransactionCreate(BaseModel):
    descricao: str = Field(..., min_length=1, max_length=500)
    valor: Decimal = Field(..., ne=0)
    card_id: UUID
    categoria_id: UUID | None = None
    period_id: UUID
    data: date
    pago: bool = False
    from_statement: bool = Field(
        default=False,
        description="True quando o lançamento veio da importação de fatura (CSV/PDF).",
    )
    installment_total: int = Field(
        default=1,
        ge=1,
        le=120,
        description="Com installment_number: uma linha (valor da parcela). Sem: >1 gera N lançamentos repartidos.",
    )
    installment_number: int | None = Field(
        default=None,
        ge=1,
        le=120,
        description="Opcional. Se informado com installment_total>1, grava só este lançamento (ex.: importação de fatura).",
    )
    auto_generate_future_installments: bool | None = Field(
        default=None,
        description=(
            "Omitido: True quando installment_number e installment_total>1 (parcela de fatura — estende nos meses seguintes). "
            "False força só o lançamento atual. Com installment_total=1 (à vista) é sempre False."
        ),
    )
    shares: list[CardTransactionShareInput] | None = Field(
        default=None,
        description="Divisão entre pessoas; soma dos valores deve igualar o valor da compra (total financiado).",
    )

    @model_validator(mode="after")
    def _resolve_auto_generate_installments(self) -> Self:
        """À vista não estende; parcela em fatura estende nos meses seguintes, salvo se enviar False."""
        if self.installment_total <= 1:
            object.__setattr__(self, "auto_generate_future_installments", False)
            return self
        auto = self.auto_generate_future_installments
        if auto is None:
            auto = self.installment_number is not None
        object.__setattr__(self, "auto_generate_future_installments", auto)
        return self


class CardTransactionUpdate(BaseModel):
    descricao: str | None = Field(None, min_length=1, max_length=500)
    valor: Decimal | None = Field(None, ne=0)
    categoria_id: UUID | None = None
    period_id: UUID | None = None
    data: date | None = None
    pago: bool | None = None
    from_statement: bool | None = None
    recorrente: bool | None = Field(
        default=None,
        description="Se true na edição, replica o lançamento para os próximos meses.",
    )
    recurrence_months: int | None = Field(
        default=None,
        ge=1,
        le=120,
        description="Quantidade de meses futuros para replicar quando recorrente=true.",
    )
    shares: list[CardTransactionShareInput] | None = Field(
        default=None,
        description="Substituir divisão; use lista vazia para remover. Omitir = não alterar.",
    )


class CardTransactionShareResponse(BaseModel):
    spender_id: UUID
    spender_nome: str
    valor: Decimal
    pago: bool = False


class CardTransactionResponse(BaseModel):
    id: UUID
    descricao: str
    valor: Decimal
    data: date
    pago: bool
    from_statement: bool
    installment_number: int
    installment_total: int
    installment_group_id: UUID | None = None
    card_id: UUID
    categoria_id: UUID | None
    categoria_nome: str | None = None
    period_id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    shares: list[CardTransactionShareResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class InvoiceTotalResponse(BaseModel):
    card_id: UUID
    period_id: UUID
    total: Decimal
    unpaid_total: Decimal = Decimal("0")
    unpaid_count: int = 0
    paid_at: date | None = None


class CardSpentTotalResponse(BaseModel):
    """Total gasto no cartão em todos os períodos (inclui parcelas)."""

    card_id: UUID
    total: Decimal


class CardTransactionsBulkDeleteResponse(BaseModel):
    card_id: UUID
    period_id: UUID
    deleted: int


class CardTransactionsBulkDeleteAllMonthsResponse(BaseModel):
    card_id: UUID
    deleted: int


class CardTransactionsMarkPaidResponse(BaseModel):
    card_id: UUID
    period_id: UUID
    updated: int
