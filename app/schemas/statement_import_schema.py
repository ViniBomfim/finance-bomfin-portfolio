from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ParsedStatementRow(BaseModel):
    data: str = Field(..., description="YYYY-MM-DD")
    descricao: str
    valor: str = Field(..., description="Decimal com ponto")
    parcela_atual: int | None = Field(default=None, description="Ex.: 8 em parcela 8/10 na fatura")
    parcela_total: int | None = Field(default=None, description="Ex.: 10 em parcela 8/10")


class ParsedStatementIgnoredRow(ParsedStatementRow):
    reason: str = Field(
        ...,
        description=(
            "Motivo de ignorar a linha no endpoint /parse: already_exists. "
            "duplicate_in_file está reservado e ainda não é emitido; "
            "o fluxo UI usa /preview (status kept/new) em vez de ignored_rows."
        ),
    )


class ParsedStatementResponse(BaseModel):
    rows: list[ParsedStatementRow]
    ignored_rows: list[ParsedStatementIgnoredRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    format_used: str = ""
    total_parsed: int = 0


class ImportPreviewRow(BaseModel):
    status: Literal["new", "kept", "updated", "skip", "orphan"]
    data: str
    descricao: str
    valor: str
    parcela_atual: int | None = None
    parcela_total: int | None = None
    existing_transaction_id: UUID | None = None
    previous_descricao: str | None = None
    previous_valor: str | None = None
    previous_data: str | None = Field(default=None, description="YYYY-MM-DD antes da atualização")
    categoria_id: UUID | None = None
    categoria_nome: str | None = None
    skip_reason: str | None = None
    update_kind: Literal["descricao", "valor", "both"] | None = None
    remove_by_default: bool = Field(
        default=False,
        description="Para status orphan: sugerir remoção no preview (marcado por padrão).",
    )


class ImportPreviewSummary(BaseModel):
    new: int = 0
    kept: int = 0
    updated: int = 0
    skip: int = 0
    orphan: int = 0
    total_in_file: int = 0


class ImportPreviewResponse(BaseModel):
    rows: list[ImportPreviewRow]
    summary: ImportPreviewSummary
    warnings: list[str] = Field(default_factory=list)
    format_used: str = ""


class ImportConfirmCreateItem(BaseModel):
    data: date
    descricao: str = Field(..., min_length=1, max_length=500)
    valor: Decimal = Field(..., ne=0)
    parcela_atual: int | None = None
    parcela_total: int | None = None
    categoria_id: UUID | None = None


class ImportConfirmUpdateItem(BaseModel):
    transaction_id: UUID
    apply: bool = True
    descricao: str | None = Field(None, min_length=1, max_length=500)
    valor: Decimal | None = Field(None, ne=0)
    data: date | None = None
    categoria_id: UUID | None = None


class ImportConfirmRequest(BaseModel):
    card_id: UUID
    period_id: UUID
    creates: list[ImportConfirmCreateItem] = Field(default_factory=list)
    updates: list[ImportConfirmUpdateItem] = Field(default_factory=list)
    deletes: list[UUID] = Field(
        default_factory=list,
        description="IDs de lançamentos from_statement órfãos a remover neste período.",
    )


class ImportConfirmResponse(BaseModel):
    created: int = 0
    updated: int = 0
    deleted: int = 0
    message: str = ""
