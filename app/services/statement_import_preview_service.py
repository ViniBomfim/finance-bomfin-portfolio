"""Classificação de linhas de fatura (novo / mantido / atualizado / ignorado) e confirmação."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.card_transaction import CardTransaction
from app.schemas.card_schema import (
    CardTransactionCreate,
    CardTransactionShareInput,
    CardTransactionUpdate,
)
from app.schemas.statement_import_schema import (
    ImportConfirmRequest,
    ImportConfirmResponse,
    ImportPreviewResponse,
    ImportPreviewRow,
    ImportPreviewSummary,
    ParsedStatementRow,
)
from app.services.card_transaction_service import CardTransactionService
from app.services.card_transaction_share_logic import SHARE_SUM_TOLERANCE, scale_shares_to_line
from app.services.card_service import CardService
from app.services.period_mutability import ensure_period_mutable, is_period_mutable
from app.services.statement_parse_service import (
    _split_itau_attached_parcela,
    extract_parcela_from_description,
)
from app.services.statement_total_rules import statement_skip_reason

PreviewStatus = Literal["new", "kept", "updated", "skip", "orphan"]
UpdateKind = Literal["descricao", "valor", "both"]


def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def resolve_desc_and_installment(
    desc: str,
    *,
    parcela_atual: int | None = None,
    parcela_total: int | None = None,
) -> tuple[str, int, int]:
    """
    Base normalizada da descrição + parcela efetiva.

    Descrições Itaú com parcela colada (``CAIEIR07/10``) sem metadados de parcela
    passam a expor ``pa/pt`` corretos. Metadados explícitos com ``pt > 1`` têm prioridade.
    """
    base, pa_from_desc, pt_from_desc = extract_parcela_from_description(desc)
    if not (pa_from_desc and pt_from_desc):
        base, pa_glue, pt_glue = _split_itau_attached_parcela(base)
        if pa_glue and pt_glue:
            pa_from_desc, pt_from_desc = pa_glue, pt_glue

    if parcela_atual and parcela_total and parcela_total > 1:
        pa, pt = parcela_atual, parcela_total
    elif pa_from_desc and pt_from_desc:
        pa, pt = pa_from_desc, pt_from_desc
    else:
        pa = parcela_atual or 1
        pt = parcela_total or 1

    key = " ".join(_strip_accents(base.strip().lower()).split())
    return key, pa, pt


def normalize_desc_key(desc: str) -> str:
    key, _, _ = resolve_desc_and_installment(desc)
    return key


def is_payment_line(desc: str) -> bool:
    """Compat: pagamento ou resumo que não deve virar lançamento."""
    return statement_skip_reason(desc) is not None


def _row_installment(row: ParsedStatementRow) -> tuple[int, int]:
    _, pa, pt = resolve_desc_and_installment(
        row.descricao,
        parcela_atual=row.parcela_atual,
        parcela_total=row.parcela_total,
    )
    return pa, pt


def _exact_key(row: ParsedStatementRow) -> tuple[str, str, str, int, int]:
    desc_key, pa, pt = resolve_desc_and_installment(
        row.descricao,
        parcela_atual=row.parcela_atual,
        parcela_total=row.parcela_total,
    )
    val = str(Decimal(row.valor).quantize(Decimal("0.01")))
    return (row.data, desc_key, val, pa, pt)


def _tx_exact_key(tx: CardTransaction) -> tuple[str, str, str, int, int]:
    desc_key, pa, pt = resolve_desc_and_installment(
        tx.descricao,
        parcela_atual=tx.installment_number,
        parcela_total=tx.installment_total,
    )
    val = str(Decimal(tx.valor).quantize(Decimal("0.01")))
    return (tx.data.isoformat(), desc_key, val, pa, pt)


def _tx_installment(tx: CardTransaction) -> tuple[int, int]:
    _, pa, pt = resolve_desc_and_installment(
        tx.descricao,
        parcela_atual=tx.installment_number,
        parcela_total=tx.installment_total,
    )
    return pa, pt


def _desc_tokens(desc: str) -> set[str]:
    s = normalize_desc_key(desc)
    return {t for t in re.findall(r"[a-z0-9]{3,}", s) if len(t) >= 3}


def descriptions_similar(a: str, b: str) -> bool:
    na, nb = normalize_desc_key(a), normalize_desc_key(b)
    if na == nb:
        return True
    if len(na) >= 5 and len(nb) >= 5 and (na in nb or nb in na):
        return True
    min_len = min(len(na), len(nb))
    if min_len >= 8 and na[:8] == nb[:8]:
        return True
    ta, tb = _desc_tokens(a), _desc_tokens(b)
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / min(len(ta), len(tb))
    return overlap >= 0.45


@dataclass
class _ExistingMatch:
    tx: CardTransaction
    exact_key: tuple[str, str, str, int, int]


def _installment_match_score(row: ParsedStatementRow, tx: CardTransaction) -> int:
    """Mesma parcela X/Y da compra no período, independente de data/valor."""
    pa, pt = _row_installment(row)
    if pt <= 1:
        return 0
    tx_pa, tx_pt = _tx_installment(tx)
    if tx_pa != pa or tx_pt != pt:
        return 0
    if normalize_desc_key(row.descricao) != normalize_desc_key(tx.descricao):
        return 0
    return 90


def _soft_match_score(row: ParsedStatementRow, tx: CardTransaction) -> int:
    pa, pt = _row_installment(row)
    if tx.data.isoformat() != row.data:
        return 0
    tx_pa, tx_pt = _tx_installment(tx)
    if tx_pa != pa or tx_pt != pt:
        return 0
    row_val = Decimal(row.valor).quantize(Decimal("0.01"))
    tx_val = Decimal(tx.valor).quantize(Decimal("0.01"))
    same_val = row_val == tx_val
    similar_desc = descriptions_similar(row.descricao, tx.descricao)
    if not similar_desc:
        return 0
    if same_val:
        return 80
    # valor diferente, descrição parecida (ex.: IOF)
    return 70


def _date_distance_days(row: ParsedStatementRow, tx: CardTransaction) -> int:
    try:
        row_d = date.fromisoformat(row.data)
    except ValueError:
        return 10_000
    return abs((tx.data - row_d).days)


def _update_kind(row: ParsedStatementRow, tx: CardTransaction) -> UpdateKind:
    row_val = Decimal(row.valor).quantize(Decimal("0.01"))
    tx_val = Decimal(tx.valor).quantize(Decimal("0.01"))
    desc_diff = normalize_desc_key(row.descricao) != normalize_desc_key(tx.descricao)
    val_diff = row_val != tx_val
    data_diff = tx.data.isoformat() != row.data
    if desc_diff and val_diff:
        return "both"
    if val_diff:
        return "valor"
    if data_diff:
        return "descricao"
    return "descricao"


def classify_statement_rows(
    parsed_rows: list[ParsedStatementRow],
    existing_txs: list[CardTransaction],
) -> list[ImportPreviewRow]:
    existing_pool: list[_ExistingMatch] = [
        _ExistingMatch(tx=tx, exact_key=_tx_exact_key(tx)) for tx in existing_txs
    ]
    exact_key_counts: dict[tuple[str, str, str, int, int], int] = {}
    for em in existing_pool:
        exact_key_counts[em.exact_key] = exact_key_counts.get(em.exact_key, 0) + 1

    file_exact_occurrence: dict[tuple[str, str, str, int, int], int] = {}
    matched_tx_ids: set[UUID] = set()
    out: list[ImportPreviewRow] = []

    for row in parsed_rows:
        skip_reason = statement_skip_reason(row.descricao)
        if skip_reason is not None:
            out.append(
                ImportPreviewRow(
                    status="skip",
                    data=row.data,
                    descricao=row.descricao,
                    valor=row.valor,
                    parcela_atual=row.parcela_atual,
                    parcela_total=row.parcela_total,
                    skip_reason=skip_reason,
                )
            )
            continue

        key = _exact_key(row)
        occ = file_exact_occurrence.get(key, 0) + 1
        file_exact_occurrence[key] = occ
        already = exact_key_counts.get(key, 0)

        if occ <= already:
            # Encontra tx correspondente para exibir categoria
            matched_tx: CardTransaction | None = None
            for em in existing_pool:
                if em.exact_key == key and em.tx.id not in matched_tx_ids:
                    matched_tx = em.tx
                    matched_tx_ids.add(em.tx.id)
                    break
            if matched_tx is None:
                for em in existing_pool:
                    if em.exact_key == key:
                        matched_tx = em.tx
                        break
            cat = matched_tx.categoria if matched_tx else None
            out.append(
                ImportPreviewRow(
                    status="kept",
                    data=row.data,
                    descricao=row.descricao,
                    valor=row.valor,
                    parcela_atual=row.parcela_atual,
                    parcela_total=row.parcela_total,
                    existing_transaction_id=matched_tx.id if matched_tx else None,
                    categoria_id=matched_tx.categoria_id if matched_tx else None,
                    categoria_nome=cat.nome if cat else None,
                )
            )
            continue

        # Soft / parcela (à vista com data diferente = novo; evita colapsar NuTag)
        # Empate de score: preferir data mais próxima.
        best: tuple[int, int, CardTransaction] | None = None
        for em in existing_pool:
            if em.tx.id in matched_tx_ids:
                continue
            for score_fn in (
                _installment_match_score,
                _soft_match_score,
            ):
                score = score_fn(row, em.tx)
                if score <= 0:
                    continue
                dist = _date_distance_days(row, em.tx)
                if best is None or score > best[0] or (score == best[0] and dist < best[1]):
                    best = (score, dist, em.tx)

        if best is not None:
            tx = best[2]
            matched_tx_ids.add(tx.id)
            cat = tx.categoria
            kind = _update_kind(row, tx)
            row_val = Decimal(row.valor).quantize(Decimal("0.01"))
            tx_val = Decimal(tx.valor).quantize(Decimal("0.01"))
            same_val = row_val == tx_val
            same_data = tx.data.isoformat() == row.data
            same_desc = normalize_desc_key(row.descricao) == normalize_desc_key(tx.descricao)
            if same_val and same_data and same_desc:
                out.append(
                    ImportPreviewRow(
                        status="kept",
                        data=row.data,
                        descricao=row.descricao,
                        valor=row.valor,
                        parcela_atual=row.parcela_atual,
                        parcela_total=row.parcela_total,
                        existing_transaction_id=tx.id,
                        categoria_id=tx.categoria_id,
                        categoria_nome=cat.nome if cat else None,
                    )
                )
                continue
            out.append(
                ImportPreviewRow(
                    status="updated",
                    data=row.data,
                    descricao=row.descricao,
                    valor=row.valor,
                    parcela_atual=row.parcela_atual,
                    parcela_total=row.parcela_total,
                    existing_transaction_id=tx.id,
                    previous_descricao=tx.descricao,
                    previous_valor=str(Decimal(tx.valor).quantize(Decimal("0.01"))),
                    previous_data=tx.data.isoformat(),
                    categoria_id=tx.categoria_id,
                    categoria_nome=cat.nome if cat else None,
                    update_kind=kind,
                )
            )
            continue

        out.append(
            ImportPreviewRow(
                status="new",
                data=row.data,
                descricao=row.descricao,
                valor=row.valor,
                parcela_atual=row.parcela_atual,
                parcela_total=row.parcela_total,
            )
        )

    # Lançamentos importados no período que não batem com nenhuma linha do arquivo.
    for tx in existing_txs:
        if tx.id in matched_tx_ids or not tx.from_statement:
            continue
        _, pa, pt = resolve_desc_and_installment(
            tx.descricao,
            parcela_atual=tx.installment_number,
            parcela_total=tx.installment_total,
        )
        cat = tx.categoria
        out.append(
            ImportPreviewRow(
                status="orphan",
                data=tx.data.isoformat(),
                descricao=tx.descricao,
                valor=str(Decimal(tx.valor).quantize(Decimal("0.01"))),
                parcela_atual=pa if pt > 1 else (tx.installment_number or None),
                parcela_total=pt if pt > 1 else (tx.installment_total or None),
                existing_transaction_id=tx.id,
                categoria_id=tx.categoria_id,
                categoria_nome=cat.nome if cat else None,
                remove_by_default=True,
            )
        )

    return out


def build_preview_summary(rows: list[ImportPreviewRow]) -> ImportPreviewSummary:
    counts = {"new": 0, "kept": 0, "updated": 0, "skip": 0, "orphan": 0}
    for r in rows:
        counts[r.status] += 1
    file_rows = counts["new"] + counts["kept"] + counts["updated"] + counts["skip"]
    return ImportPreviewSummary(
        new=counts["new"],
        kept=counts["kept"],
        updated=counts["updated"],
        skip=counts["skip"],
        orphan=counts["orphan"],
        total_in_file=file_rows,
    )


class StatementImportPreviewService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.card_txs = CardTransactionService(db)

    def preview(
        self,
        user_id: UUID,
        card_id: UUID,
        period_id: UUID,
        parsed_rows: list[ParsedStatementRow],
    ) -> ImportPreviewResponse:
        existing = self.card_txs.list_card_expenses_for_import(user_id, card_id, period_id)
        classified = classify_statement_rows(parsed_rows, existing)
        return ImportPreviewResponse(
            rows=classified,
            summary=build_preview_summary(classified),
            warnings=[],
            format_used="",
        )

    def confirm(self, user_id: UUID, data: ImportConfirmRequest) -> ImportConfirmResponse:
        CardService(self.db).get(user_id, data.card_id)
        period = self.card_txs.periods.get_by_id(data.period_id, user_id)
        if period is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        ensure_period_mutable(self.db, user_id, data.period_id)

        simple_creates: list[CardTransactionCreate] = []
        complex_creates: list[CardTransactionCreate] = []
        # Creates que na verdade já existem (ex.: parcela X/Y já lançada).
        diverted_updates: list[tuple[UUID, CardTransactionCreate]] = []
        claimed_existing_ids: set[UUID] = set()

        for item in data.creates:
            pa = item.parcela_atual
            pt = item.parcela_total
            parcela_na_fatura = pt is not None and pt > 1 and pa is not None and pa >= 1 and pa <= pt
            inum = pa if parcela_na_fatura else 1
            itotal = pt if parcela_na_fatura and pt else 1
            body = CardTransactionCreate(
                descricao=item.descricao.strip(),
                valor=Decimal(item.valor),
                card_id=data.card_id,
                categoria_id=item.categoria_id,
                period_id=data.period_id,
                data=item.data,
                pago=False,
                from_statement=True,
                installment_total=itotal,
                installment_number=pa if parcela_na_fatura else None,
                auto_generate_future_installments=parcela_na_fatura,
                shares=[],
            )
            existing = self.card_txs.txs.find_matching_for_import(
                user_id=user_id,
                card_id=data.card_id,
                period_id=data.period_id,
                descricao=body.descricao,
                valor=body.valor,
                data_iso=body.data,
                installment_number=inum,
                installment_total=itotal,
                exclude_ids=claimed_existing_ids,
            )
            if existing is not None:
                claimed_existing_ids.add(existing.id)
                diverted_updates.append((existing.id, body))
                continue
            if parcela_na_fatura:
                complex_creates.append(body)
            else:
                simple_creates.append(body)

        category_ids = {
            b.categoria_id
            for b in (*simple_creates, *complex_creates, *(b for _, b in diverted_updates))
            if b.categoria_id is not None
        }
        for categoria_id in category_ids:
            self.card_txs._ensure_expense_category(user_id, categoria_id)

        created = 0
        updated = 0
        affected_periods: set[UUID] = {data.period_id}

        if simple_creates:
            self.card_txs.create_simple_import_batch(user_id, simple_creates, commit=False)
            created += len(simple_creates)

        for body in complex_creates:
            rows = self.card_txs.create(
                user_id, body, commit=False, reload=False, skip_preflight=True
            )
            created += 1
            for row in rows:
                affected_periods.add(row.period_id)

        for existing_id, body in diverted_updates:
            if not is_period_mutable(self.db, user_id, data.period_id):
                continue
            existing_tx = self.card_txs.txs.get_by_id(existing_id, user_id)
            patch = CardTransactionUpdate(
                from_statement=True,
                descricao=body.descricao,
                valor=body.valor,
                data=body.data,
            )
            if body.categoria_id is not None:
                patch.categoria_id = body.categoria_id
            # Reescala divisão se o valor mudou (mesmo fluxo dos updates explícitos).
            if existing_tx is not None and abs(body.valor - existing_tx.valor) > SHARE_SUM_TOLERANCE:
                existing_shares = self.card_txs.shares.list_for_transaction(existing_id)
                if existing_shares:
                    pairs = [(s.spender_id, s.valor) for s in existing_shares]
                    scaled = scale_shares_to_line(pairs, body.valor, existing_tx.valor)
                    patch.shares = [
                        CardTransactionShareInput(spender_id=sid, valor=v) for sid, v in scaled
                    ]
            tx = self.card_txs.update(
                user_id, existing_id, patch, commit=False, reload=False
            )
            affected_periods.add(tx.period_id)
            updated += 1

        update_tx_ids = [item.transaction_id for item in data.updates if item.transaction_id]
        tx_by_id: dict[UUID, CardTransaction] = {}
        if update_tx_ids:
            for tx_id in update_tx_ids:
                tx = self.card_txs.txs.get_by_id(tx_id, user_id)
                if tx is not None:
                    tx_by_id[tx_id] = tx

        for item in data.updates:
            if not item.transaction_id:
                continue
            if item.transaction_id in claimed_existing_ids:
                # Já tratado como diverted create→update.
                continue
            tx = tx_by_id.get(item.transaction_id)
            if tx is None:
                continue
            if not is_period_mutable(self.db, user_id, tx.period_id):
                continue
            if not item.apply:
                if not tx.from_statement:
                    self.card_txs.update(
                        user_id,
                        item.transaction_id,
                        CardTransactionUpdate(from_statement=True),
                        commit=False,
                        reload=False,
                    )
                    affected_periods.add(tx.period_id)
                continue
            patch = CardTransactionUpdate(from_statement=True)
            if item.descricao is not None:
                patch.descricao = item.descricao.strip()
            if item.valor is not None:
                new_valor = Decimal(item.valor)
                patch.valor = new_valor
                # Importação não envia shares: reescala as partes para o novo valor.
                if abs(new_valor - tx.valor) > SHARE_SUM_TOLERANCE:
                    existing_shares = self.card_txs.shares.list_for_transaction(tx.id)
                    if existing_shares:
                        pairs = [(s.spender_id, s.valor) for s in existing_shares]
                        scaled = scale_shares_to_line(pairs, new_valor, tx.valor)
                        patch.shares = [
                            CardTransactionShareInput(spender_id=sid, valor=v) for sid, v in scaled
                        ]
            if item.categoria_id is not None:
                patch.categoria_id = item.categoria_id
            if item.data is not None:
                patch.data = item.data
            tx = self.card_txs.update(
                user_id, item.transaction_id, patch, commit=False, reload=False
            )
            affected_periods.add(tx.period_id)
            updated += 1

        deleted = 0
        if data.deletes:
            # Só remove from_statement do mesmo cartão/período (órfãos da reimportação).
            delete_ids: list[UUID] = []
            for tx_id in data.deletes:
                tx = self.card_txs.txs.get_by_id(tx_id, user_id)
                if tx is None:
                    continue
                if tx.card_id != data.card_id or tx.period_id != data.period_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Lançamento fora do cartão/período da importação.",
                    )
                if not tx.from_statement:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Só é possível remover lançamentos importados da fatura.",
                    )
                if not is_period_mutable(self.db, user_id, tx.period_id):
                    continue
                delete_ids.append(tx.id)
            if delete_ids:
                deleted = self.card_txs.txs.delete_by_ids(user_id, delete_ids, commit=False)
                affected_periods.add(data.period_id)

        self.card_txs._finalize_batch(user_id, affected_periods)

        parts: list[str] = []
        if created:
            parts.append(f"{created} novo(s)")
        if updated:
            parts.append(f"{updated} atualizado(s)")
        if deleted:
            parts.append(f"{deleted} removido(s)")
        message = (
            "Importação confirmada: " + ", ".join(parts) + "."
            if parts
            else "Nenhuma alteração aplicada."
        )
        return ImportConfirmResponse(
            created=created,
            updated=updated,
            deleted=deleted,
            message=message,
        )
