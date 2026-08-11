from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DebtorLoanCreate(BaseModel):
    devedor_nome: str = Field(..., min_length=1, max_length=200)
    valor_emprestado: Decimal = Field(..., gt=0)
    data_emprestimo: date
    destino_dinheiro: str = Field(..., min_length=1, max_length=500)
    observacoes: str | None = Field(None, max_length=2000)
    spender_id: UUID | None = None


class DebtorLoanUpdate(BaseModel):
    devedor_nome: str | None = Field(None, min_length=1, max_length=200)
    valor_emprestado: Decimal | None = Field(None, gt=0)
    data_emprestimo: date | None = None
    destino_dinheiro: str | None = Field(None, min_length=1, max_length=500)
    observacoes: str | None = Field(None, max_length=2000)
    spender_id: UUID | None = None


class DebtorPaymentCreate(BaseModel):
    data_pagamento: date
    valor_pago: Decimal = Field(..., gt=0)
    observacao: str | None = Field(None, max_length=500)


class DebtorPaymentResponse(BaseModel):
    id: UUID
    data_pagamento: date
    valor_pago: Decimal
    observacao: str | None
    emprestimo_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DebtorLoanResponse(BaseModel):
    id: UUID
    devedor_nome: str
    valor_emprestado: Decimal
    data_emprestimo: date
    destino_dinheiro: str
    observacoes: str | None
    user_id: UUID
    spender_id: UUID | None = None
    spender_nome: str | None = None
    valor_pago: Decimal
    valor_restante: Decimal
    status: Literal["pendente", "quitado"]
    ultimo_pagamento_em: date | None = None
    dias_sem_pagamento: int | None = None
    pagamentos: list[DebtorPaymentResponse]
    created_at: datetime
    updated_at: datetime
