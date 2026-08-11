import unicodedata
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.schemas.statement_import_schema import (
    ImportConfirmRequest,
    ImportConfirmResponse,
    ImportPreviewResponse,
    ParsedStatementIgnoredRow,
    ParsedStatementResponse,
    ParsedStatementRow,
)
from app.services.card_transaction_service import CardTransactionService
from app.services.statement_import_preview_service import StatementImportPreviewService
from app.services.statement_parse_service import extract_parcela_from_description, parse_statement_file

router = APIRouter(prefix="/statement-import", tags=["statement-import"])


ALLOWED_FORMATS = frozenset(
    {
        "generic_csv",
        "nubank_csv",
        "santander_csv",
        "itau_azul_csv",
        "itau_pda_csv",
        "pdf_br",
        "nubank_pdf",
        "santander_pdf",
        "itau_azul_pdf",
        "itau_pda_pdf",
    }
)


def _normalize_desc_key(desc: str) -> str:
    """Alinha com o front (NFD + remoção de acentos) para chave de deduplicação."""
    base, _, _ = extract_parcela_from_description(desc)
    s = base.strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


def _statement_row_key(row: ParsedStatementRow) -> tuple[str, str, str, int, int]:
    pa = row.parcela_atual or 1
    pt = row.parcela_total or 1
    val = str(Decimal(row.valor).quantize(Decimal("0.01")))
    return (row.data, _normalize_desc_key(row.descricao), val, pa, pt)


def _parse_upload(
    content: bytes,
    filename: str,
    format_id: str,
    default_date: str | None,
) -> tuple[list[ParsedStatementRow], list[str]]:
    rows, warnings = parse_statement_file(content, filename, format_id, default_date)
    parsed: list[ParsedStatementRow] = []
    for r in rows:
        desc, pa, pt = extract_parcela_from_description(r.descricao)
        parsed.append(
            ParsedStatementRow(
                data=r.data,
                descricao=desc[:500],
                valor=r.valor,
                parcela_atual=pa,
                parcela_total=pt,
            )
        )
    return parsed, warnings


@router.post("/parse", response_model=ParsedStatementResponse)
async def parse_statement(
    _user_id: CurrentUserId,
    file: UploadFile = File(...),
    format_id: str = Form("generic_csv"),
    default_date: str | None = Form(None),
    card_id: UUID | None = Form(None),
    period_id: UUID | None = Form(None),
    db: Session = Depends(get_db),
) -> ParsedStatementResponse:
    if format_id not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"format_id inválido. Use: {', '.join(sorted(ALLOWED_FORMATS))}",
        )
    if (card_id is None) != (period_id is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Envie card_id e period_id juntos para deduplicar importação de cartão.",
        )
    content = await file.read()
    parsed, warnings = _parse_upload(
        content,
        file.filename or "upload",
        format_id,
        default_date.strip() if default_date else None,
    )
    total_parsed = len(parsed)
    ignored_rows: list[ParsedStatementIgnoredRow] = []
    if card_id is not None and period_id is not None:
        existing = CardTransactionService(db).list_card_expenses_for_import(_user_id, card_id, period_id)
        existing_counts: dict[tuple[str, str, str, int, int], int] = {}
        for tx in existing:
            tx_val = str(Decimal(tx.valor).quantize(Decimal("0.01")))
            k = (
                tx.data.isoformat(),
                _normalize_desc_key(tx.descricao),
                tx_val,
                tx.installment_number or 1,
                tx.installment_total or 1,
            )
            existing_counts[k] = existing_counts.get(k, 0) + 1
        deduped: list[ParsedStatementRow] = []
        file_occurrence: dict[tuple[str, str, str, int, int], int] = {}
        skipped_as_duplicate_count = 0
        for row in parsed:
            key = _statement_row_key(row)
            occ = file_occurrence.get(key, 0) + 1
            file_occurrence[key] = occ
            already = existing_counts.get(key, 0)
            if occ <= already:
                skipped_as_duplicate_count += 1
                ignored_rows.append(
                    ParsedStatementIgnoredRow(
                        data=row.data,
                        descricao=row.descricao,
                        valor=row.valor,
                        parcela_atual=row.parcela_atual,
                        parcela_total=row.parcela_total,
                        reason="already_exists",
                    )
                )
                continue
            deduped.append(row)
        parsed = deduped
        if skipped_as_duplicate_count > 0:
            warnings.append(
                f"{skipped_as_duplicate_count} linha(s) já coberta(s) por lançamentos nesta fatura "
                "(incluindo repetições na fatura, ex.: pedágios) foram ignoradas automaticamente."
            )
    return ParsedStatementResponse(
        rows=parsed,
        ignored_rows=ignored_rows,
        warnings=warnings,
        format_used=format_id,
        total_parsed=total_parsed,
    )


@router.post("/preview", response_model=ImportPreviewResponse)
async def preview_statement(
    _user_id: CurrentUserId,
    file: UploadFile = File(...),
    format_id: str = Form("generic_csv"),
    default_date: str | None = Form(None),
    card_id: UUID = Form(...),
    period_id: UUID = Form(...),
    db: Session = Depends(get_db),
) -> ImportPreviewResponse:
    if format_id not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"format_id inválido. Use: {', '.join(sorted(ALLOWED_FORMATS))}",
        )
    content = await file.read()
    parsed, warnings = _parse_upload(
        content,
        file.filename or "upload",
        format_id,
        default_date.strip() if default_date else None,
    )
    if not parsed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma linha reconhecida no arquivo.",
        )
    svc = StatementImportPreviewService(db)
    result = svc.preview(_user_id, card_id, period_id, parsed)
    result.warnings = warnings
    result.format_used = format_id
    return result


@router.post("/confirm", response_model=ImportConfirmResponse)
def confirm_statement_import(
    _user_id: CurrentUserId,
    body: ImportConfirmRequest,
    db: Session = Depends(get_db),
) -> ImportConfirmResponse:
    if not body.creates and not body.updates and not body.deletes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma ação de importação informada.",
        )
    result = StatementImportPreviewService(db).confirm(_user_id, body)
    return result


@router.get("/formats")
def list_formats(_user_id: CurrentUserId) -> list[dict[str, str | list[str]]]:
    return [
        {
            "id": "generic_csv",
            "label": "CSV genérico (Itaú, Bradesco, etc.)",
            "files": ["csv", "txt"],
        },
        {
            "id": "nubank_csv",
            "label": "CSV Nubank / fintech (date, title, amount)",
            "files": ["csv", "txt"],
        },
        {
            "id": "santander_csv",
            "label": "CSV Santander",
            "files": ["csv", "txt"],
        },
        {
            "id": "itau_azul_csv",
            "label": "CSV Itaú Azul",
            "files": ["csv", "txt"],
        },
        {
            "id": "itau_pda_csv",
            "label": "CSV Itaú PDA",
            "files": ["csv", "txt"],
        },
        {
            "id": "nubank_pdf",
            "label": "PDF Nubank",
            "files": ["pdf"],
        },
        {
            "id": "pdf_br",
            "label": "PDF — texto extraído (fatura digital)",
            "files": ["pdf"],
        },
        {
            "id": "santander_pdf",
            "label": "PDF Santander",
            "files": ["pdf"],
        },
        {
            "id": "itau_azul_pdf",
            "label": "PDF Itaú Azul",
            "files": ["pdf"],
        },
        {
            "id": "itau_pda_pdf",
            "label": "PDF Itaú PDA",
            "files": ["pdf"],
        },
    ]
