from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

InvestmentTipo = Literal["renda_fixa", "stock", "fii", "crypto"]


class InvestmentCreate(BaseModel):
    listed_asset_id: UUID | None = None
    descricao: str | None = Field(None, max_length=200)
    tipo: InvestmentTipo | None = None
    valor_aplicado: Decimal = Field(default=Decimal("0"), ge=0)
    valor_atual: Decimal = Field(default=Decimal("0"), ge=0)
    quantidade: Decimal | None = Field(default=None, gt=0)
    preco_medio: Decimal | None = Field(default=None, ge=0)
    preco_unitario_atual: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def catalog_or_manual(self):
        if self.listed_asset_id is not None:
            return self
        if not self.descricao or not str(self.descricao).strip():
            raise ValueError("Informe a descrição ou escolha um ativo do cadastro.")
        if self.tipo is None:
            raise ValueError("Informe o tipo ou escolha um ativo do cadastro.")
        return self


class InvestmentUpdate(BaseModel):
    listed_asset_id: UUID | None = None
    descricao: str | None = Field(None, min_length=1, max_length=200)
    tipo: InvestmentTipo | None = None
    valor_aplicado: Decimal | None = Field(None, ge=0)
    valor_atual: Decimal | None = Field(None, ge=0)
    quantidade: Decimal | None = Field(default=None, gt=0)
    preco_medio: Decimal | None = Field(default=None, ge=0)
    preco_unitario_atual: Decimal | None = Field(default=None, ge=0)


class InvestmentResponse(BaseModel):
    id: UUID
    descricao: str
    tipo: str
    valor_aplicado: Decimal
    valor_atual: Decimal
    quantidade: Decimal | None
    preco_medio: Decimal | None
    preco_unitario_atual: Decimal | None
    listed_asset_id: UUID | None
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
