import logging
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.card_transaction import CardTransaction
from app.models.card_transaction_share import CardTransactionShare
from app.repositories.card_repository import CardRepository
from app.repositories.card_transaction_repository import CardTransactionRepository
from app.repositories.card_transaction_share_repository import CardTransactionShareRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.period_repository import PeriodRepository
from app.repositories.spender_repository import SpenderRepository
from app.schemas.card_schema import CardTransactionCreate, CardTransactionShareInput, CardTransactionUpdate
from app.schemas.card_spender_summary_schema import (
    CardSpenderSummaryResponse,
    SpenderSummaryGroup,
    SpenderSummaryLine,
)
from app.services.card_service import CardService
from app.services.card_transaction_share_logic import (
    SHARE_SUM_TOLERANCE,
    attach_pago,
    normalize_share_template,
    scale_shares_to_line,
)
from app.services.period_mutability import ensure_period_mutable, is_period_mutable
from app.services.period_service import PeriodService
from app.services.card_split_template_service import CardSplitTemplateService
from app.services.dashboard_cache import DashboardCache
from app.services.statement_parse_service import canonical_card_description
from app.services.date_utils import date_in_month

logger = logging.getLogger(__name__)


class CardTransactionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.txs = CardTransactionRepository(db)
        self.periods = PeriodRepository(db)
        self.cards = CardRepository(db)
        self.categories = CategoryRepository(db)
        self.spenders = SpenderRepository(db)
        self.shares = CardTransactionShareRepository(db)
        self._split_tpl = CardSplitTemplateService(db)

    def _share_inputs_for_create(
        self, user_id: UUID, data: CardTransactionCreate, canon_desc: str
    ) -> list[CardTransactionShareInput] | None:
        # [] enviado explicitamente significa "sem divisão" (não aplicar template automático).
        if data.shares is not None:
            return data.shares
        pairs = self._split_tpl.pairs_for_valor(user_id, data.card_id, canon_desc, data.valor)
        if not pairs:
            return None
        return [CardTransactionShareInput(spender_id=sid, valor=v) for sid, v in pairs]

    def _persist_split_template(
        self,
        user_id: UUID,
        card_id: UUID,
        canon_desc: str,
        template: list[tuple[UUID, Decimal]] | list[tuple[UUID, Decimal, bool]],
        total_valor: Decimal,
        *,
        commit: bool = True,
    ) -> None:
        if not template:
            return
        amount_pairs = [(row[0], row[1]) for row in template]
        self._split_tpl.save_from_pairs(user_id, card_id, canon_desc, amount_pairs, total_valor, commit=commit)

    def _shares_for_replace(
        self,
        pairs: list[tuple[UUID, Decimal]] | list[tuple[UUID, Decimal, bool]] | None,
        *,
        force_pago: bool | None = None,
    ) -> list[tuple[UUID, Decimal, bool]]:
        if not pairs:
            return []
        out: list[tuple[UUID, Decimal, bool]] = []
        for row in pairs:
            sid, val = row[0], row[1]
            if force_pago is not None:
                pago = force_pago
            elif len(row) == 3:
                pago = bool(row[2])  # type: ignore[misc]
            else:
                pago = False
            out.append((sid, val, pago))
        return out

    def _ensure_expense_category(self, user_id: UUID, categoria_id: UUID) -> None:
        cat = self.categories.get_by_id(categoria_id, user_id)
        if cat is None or cat.tipo != "expense":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Categoria de despesa inválida",
            )

    def _replace_shares(
        self,
        card_transaction_id: UUID,
        pairs: list[tuple[UUID, Decimal]] | list[tuple[UUID, Decimal, bool]],
        *,
        commit: bool = True,
        default_pago: bool = False,
    ) -> None:
        self.shares.delete_for_transaction(card_transaction_id, commit=commit)
        if not pairs:
            return
        rows: list[CardTransactionShare] = []
        for row in pairs:
            if len(row) == 3:
                sid, v, pago = row  # type: ignore[misc]
            else:
                sid, v = row  # type: ignore[misc]
                pago = default_pago
            rows.append(
                CardTransactionShare(
                    card_transaction_id=card_transaction_id,
                    spender_id=sid,
                    valor=v,
                    pago=bool(pago),
                )
            )
        self.shares.create_many(rows, commit=commit)

    def _sync_tx_pago_from_shares(self, tx: CardTransaction, *, commit: bool = True) -> CardTransaction:
        loaded = self.shares.list_for_transaction(tx.id)
        if not loaded:
            return tx
        tx.pago = all(bool(sh.pago) for sh in loaded)
        return self.txs.update(tx, commit=commit)

    def _reload(self, tx_id: UUID, user_id: UUID) -> CardTransaction:
        tx = self.txs.get_by_id(tx_id, user_id)
        if tx is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
        return tx

    def _validate_existing_shares_match_valor(self, tx: CardTransaction) -> None:
        loaded = self.shares.list_for_transaction(tx.id)
        if not loaded:
            return
        s = sum((sh.valor for sh in loaded), Decimal("0"))
        if abs(s - tx.valor) > SHARE_SUM_TOLERANCE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A divisão entre pessoas não bate com o novo valor. Atualize as partes.",
            )

    def _replicate_as_recurring(
        self,
        *,
        user_id: UUID,
        source_tx: CardTransaction,
        recurrence_months: int,
    ) -> None:
        if recurrence_months <= 0:
            return
        if source_tx.installment_total > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recorrência na edição só é permitida para lançamentos sem parcelamento.",
            )

        seq = PeriodService(self.db).ensure_calendar_periods_from_start(
            user_id, source_tx.period_id, recurrence_months + 1
        )
        if len(seq) <= 1:
            return

        for p in seq[1:]:
            ensure_period_mutable(self.db, user_id, p.id)

        day = source_tx.data.day
        share_pairs = [(s.spender_id, s.valor) for s in (source_tx.shares or [])]
        to_create: list[CardTransaction] = []
        for period in seq[1:]:
            target_date = date_in_month(period.ano, period.mes, day)
            existing = self.txs.find_matching_single_charge(
                user_id=user_id,
                card_id=source_tx.card_id,
                period_id=period.id,
                descricao=source_tx.descricao,
                valor=source_tx.valor,
                data_iso=target_date,
            )
            if existing is not None:
                continue
            to_create.append(
                CardTransaction(
                    descricao=source_tx.descricao,
                    valor=source_tx.valor,
                    data=target_date,
                    pago=False,
                    from_statement=False,
                    installment_number=1,
                    installment_total=1,
                    card_id=source_tx.card_id,
                    categoria_id=source_tx.categoria_id,
                    period_id=period.id,
                    user_id=user_id,
                )
            )

        created = self.txs.create_many(to_create) if to_create else []
        for row in created:
            self._replace_shares(row.id, share_pairs)

    def _merge_missing_fields_from_import(
        self,
        user_id: UUID,
        existing: CardTransaction,
        data: CardTransactionCreate,
        *,
        commit: bool = True,
        reload: bool = True,
    ) -> CardTransaction:
        """Reimport sem duplicar: preenche apenas campos faltantes no lançamento já existente."""
        if not is_period_mutable(self.db, user_id, existing.period_id):
            if reload:
                return self._reload(existing.id, user_id)
            return existing
        changed = False
        if existing.categoria_id is None and data.categoria_id is not None:
            ensure_period_mutable(self.db, user_id, existing.period_id)
            existing.categoria_id = data.categoria_id
            changed = True
        if data.from_statement and not existing.from_statement:
            ensure_period_mutable(self.db, user_id, existing.period_id)
            existing.from_statement = True
            changed = True
        if data.from_statement:
            if data.valor != existing.valor:
                ensure_period_mutable(self.db, user_id, existing.period_id)
                existing.valor = data.valor
                changed = True
            if data.data != existing.data:
                ensure_period_mutable(self.db, user_id, existing.period_id)
                existing.data = data.data
                changed = True
        loaded_sh = self.shares.list_for_transaction(existing.id)
        if (
            existing.installment_total > 1
            and existing.installment_number > 1
            and (existing.categoria_id is None or not loaded_sh)
        ):
            ref = self.txs.find_installment_propagation_source(
                user_id=user_id,
                card_id=existing.card_id,
                descricao=existing.descricao,
                valor=existing.valor,
                installment_total=existing.installment_total,
                before_installment_number=existing.installment_number,
            )
            if ref is not None:
                if existing.categoria_id is None and ref.categoria_id is not None:
                    self._ensure_expense_category(user_id, ref.categoria_id)
                    ensure_period_mutable(self.db, user_id, existing.period_id)
                    existing.categoria_id = ref.categoria_id
                    changed = True
                if not loaded_sh:
                    ref_pairs = [(s.spender_id, s.valor) for s in self.shares.list_for_transaction(ref.id)]
                    if ref_pairs and ref.valor and ref.valor != 0:
                        scaled = scale_shares_to_line(ref_pairs, existing.valor, ref.valor)
                        if scaled:
                            ensure_period_mutable(self.db, user_id, existing.period_id)
                            self._replace_shares(existing.id, scaled, commit=commit)
                            changed = True
        if changed:
            self.txs.update(existing, commit=commit)
        if reload:
            return self._reload(existing.id, user_id)
        return existing

    def _finalize_batch(self, user_id: UUID, period_ids: set[UUID]) -> None:
        self.db.commit()
        for period_id in period_ids:
            DashboardCache.invalidate_user_period(user_id, period_id)

    def create_simple_import_batch(
        self,
        user_id: UUID,
        items: list[CardTransactionCreate],
        *,
        commit: bool = True,
    ) -> list[CardTransaction]:
        """Insere lançamentos simples (1/1) de fatura em lote, sem lógica de parcelas/shares."""
        if not items:
            return []
        out: list[CardTransaction] = []
        for data in items:
            canon_desc = canonical_card_description(data.descricao)
            out.append(
                CardTransaction(
                    descricao=canon_desc,
                    valor=data.valor,
                    data=data.data,
                    pago=data.pago,
                    from_statement=data.from_statement,
                    installment_number=1,
                    installment_total=1,
                    card_id=data.card_id,
                    categoria_id=data.categoria_id,
                    period_id=data.period_id,
                    user_id=user_id,
                )
            )
        return self.txs.create_many(out, commit=commit)

    def create(
        self,
        user_id: UUID,
        data: CardTransactionCreate,
        *,
        commit: bool = True,
        reload: bool = True,
        skip_preflight: bool = False,
    ) -> list[CardTransaction]:
        if not skip_preflight:
            CardService(self.db).get(user_id, data.card_id)
            p = self.periods.get_by_id(data.period_id, user_id)
            if p is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
            ensure_period_mutable(self.db, user_id, data.period_id)
        total = data.installment_total
        inum = data.installment_number
        canon_desc = canonical_card_description(data.descricao)

        share_inputs = self._share_inputs_for_create(user_id, data, canon_desc)
        template = normalize_share_template(user_id, self.spenders, share_inputs, data.valor)
        prop_cat = data.categoria_id
        prop_tpl = template
        if total > 1 and inum is not None:
            ref_tx = self.txs.find_installment_propagation_source(
                user_id=user_id,
                card_id=data.card_id,
                descricao=canon_desc,
                valor=data.valor,
                installment_total=total,
                before_installment_number=inum,
            )
            if ref_tx is not None:
                if prop_cat is None and ref_tx.categoria_id is not None:
                    prop_cat = ref_tx.categoria_id
                if not prop_tpl:
                    ref_pairs = [(s.spender_id, s.valor) for s in (ref_tx.shares or [])]
                    if not ref_pairs:
                        ref_pairs = [(s.spender_id, s.valor) for s in self.shares.list_for_transaction(ref_tx.id)]
                    if ref_pairs and ref_tx.valor != 0:
                        prop_tpl = scale_shares_to_line(ref_pairs, data.valor, ref_tx.valor)
        if prop_cat is not None:
            self._ensure_expense_category(user_id, prop_cat)

        if total <= 1:
            tx = CardTransaction(
                descricao=canon_desc,
                valor=data.valor,
                data=data.data,
                pago=data.pago,
                from_statement=data.from_statement,
                installment_number=1,
                installment_total=1,
                card_id=data.card_id,
                categoria_id=prop_cat,
                period_id=data.period_id,
                user_id=user_id,
            )
            tx = self.txs.create(tx, commit=commit)
            if prop_tpl:
                self._replace_shares(
                    tx.id,
                    self._shares_for_replace(prop_tpl, force_pago=True if data.pago else None),
                    commit=commit,
                )
            self._persist_split_template(user_id, data.card_id, canon_desc, prop_tpl, data.valor, commit=commit)
            created = self._reload(tx.id, user_id) if reload else tx
            if reload and getattr(created, "shares", None):
                created = self._sync_tx_pago_from_shares(created, commit=commit)
            return [created]

        if inum is not None:
            if inum > total:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="installment_number não pode ser maior que installment_total",
                )
            if data.auto_generate_future_installments:
                remaining = total - inum + 1
                seq = PeriodService(self.db).ensure_calendar_periods_from_start(user_id, data.period_id, remaining)
                for sp in seq:
                    ensure_period_mutable(self.db, user_id, sp.id)
                installment_numbers = [inum + i for i in range(remaining)]
                existing = self.txs.list_existing_installments(
                    user_id=user_id,
                    card_id=data.card_id,
                    descricao=canon_desc,
                    valor=data.valor,
                    data_iso=data.data,
                    installment_total=total,
                    period_ids=[sp.id for sp in seq],
                    installment_numbers=installment_numbers,
                )
                period_ids = [sp.id for sp in seq]
                existing_by_signature = self.txs.list_similar_rows_for_import(
                    user_id=user_id,
                    card_id=data.card_id,
                    descricao=canon_desc,
                    valor=data.valor,
                    data_iso=data.data,
                    installment_total=total,
                    period_ids=period_ids,
                )
                existing_ids = {e.id for e in existing}
                all_existing = existing + [x for x in existing_by_signature if x.id not in existing_ids]
                existing_keys = {(x.period_id, x.installment_number) for x in existing}
                # Vincula todas as parcelas desta compra pelo mesmo group_id (reaproveita o já existente).
                group_id = next(
                    (x.installment_group_id for x in all_existing if x.installment_group_id is not None),
                    None,
                ) or uuid4()
                for ex in existing:
                    self._merge_missing_fields_from_import(user_id, ex, data, commit=commit, reload=reload)
                for ex in all_existing:
                    if ex.id not in existing_ids:
                        self._merge_missing_fields_from_import(user_id, ex, data, commit=commit, reload=reload)
                for ex in all_existing:
                    if ex.installment_group_id != group_id:
                        ex.installment_group_id = group_id
                        self.txs.update(ex, commit=commit)
                out: list[CardTransaction] = []
                for i in range(remaining):
                    installment_number = inum + i
                    period_id = seq[i].id
                    if (period_id, installment_number) in existing_keys:
                        continue
                    tx = CardTransaction(
                        descricao=canon_desc,
                        valor=data.valor,
                        data=data.data,
                        pago=data.pago,
                        from_statement=data.from_statement,
                        installment_number=installment_number,
                        installment_total=total,
                        installment_group_id=group_id,
                        card_id=data.card_id,
                        categoria_id=prop_cat,
                        period_id=period_id,
                        user_id=user_id,
                    )
                    out.append(tx)
                created = self.txs.create_many(out, commit=commit) if out else []
                if prop_tpl:
                    for t in created:
                        self._replace_shares(
                            t.id,
                            self._shares_for_replace(prop_tpl, force_pago=True if data.pago else None),
                            commit=commit,
                        )
                if reload:
                    reloaded_existing = [self._reload(x.id, user_id) for x in all_existing]
                    reloaded_created = []
                    for x in created:
                        row = self._reload(x.id, user_id)
                        if row.shares:
                            row = self._sync_tx_pago_from_shares(row, commit=commit)
                        reloaded_created.append(row)
                    result = [*reloaded_existing, *reloaded_created]
                else:
                    result = [*all_existing, *created]
                self._persist_split_template(
                    user_id, data.card_id, canon_desc, prop_tpl, data.valor, commit=commit
                )
                return result
            existing_single = self.txs.find_matching_for_import(
                user_id=user_id,
                card_id=data.card_id,
                period_id=data.period_id,
                descricao=canon_desc,
                valor=data.valor,
                data_iso=data.data,
                installment_number=inum,
                installment_total=total,
            )
            # Reaproveita o grupo da parcela anterior (se houver) para manter a compra ligada.
            group_id = (
                ref_tx.installment_group_id
                if ref_tx is not None and ref_tx.installment_group_id is not None
                else None
            ) or uuid4()
            if existing_single is not None:
                if existing_single.installment_group_id is None:
                    existing_single.installment_group_id = group_id
                    self.txs.update(existing_single, commit=commit)
                merged = self._merge_missing_fields_from_import(
                    user_id, existing_single, data, commit=commit, reload=reload
                )
                return [merged]
            tx = CardTransaction(
                descricao=canon_desc,
                valor=data.valor,
                data=data.data,
                pago=data.pago,
                from_statement=data.from_statement,
                installment_number=inum,
                installment_total=total,
                installment_group_id=group_id,
                card_id=data.card_id,
                categoria_id=prop_cat,
                period_id=data.period_id,
                user_id=user_id,
            )
            tx = self.txs.create(tx, commit=commit)
            if prop_tpl:
                self._replace_shares(
                    tx.id,
                    self._shares_for_replace(prop_tpl, force_pago=True if data.pago else None),
                    commit=commit,
                )
            self._persist_split_template(user_id, data.card_id, canon_desc, prop_tpl, data.valor, commit=commit)
            created = self._reload(tx.id, user_id) if reload else tx
            if reload and getattr(created, "shares", None):
                created = self._sync_tx_pago_from_shares(created, commit=commit)
            return [created]

        seq = PeriodService(self.db).ensure_calendar_periods_from_start(user_id, data.period_id, total)
        for sp in seq:
            ensure_period_mutable(self.db, user_id, sp.id)
        unit = (data.valor / Decimal(total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        group_id = uuid4()
        out: list[CardTransaction] = []
        running = Decimal("0")
        for i in range(total):
            val = unit if i < total - 1 else (data.valor - running).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            running += val
            tx = CardTransaction(
                descricao=canon_desc,
                valor=val,
                data=data.data,
                pago=data.pago,
                from_statement=data.from_statement,
                installment_number=i + 1,
                installment_total=total,
                installment_group_id=group_id,
                card_id=data.card_id,
                categoria_id=prop_cat,
                period_id=seq[i].id,
                user_id=user_id,
            )
            out.append(tx)
        created = self.txs.create_many(out, commit=commit)
        if prop_tpl:
            pago_map = {
                p[0]: (True if data.pago else (p[2] if len(p) == 3 else False))  # type: ignore[misc]
                for p in prop_tpl
            }
            for t in created:
                line_pairs = scale_shares_to_line(prop_tpl, t.valor, data.valor)
                self._replace_shares(
                    t.id,
                    attach_pago(line_pairs, pago_map, default_pago=bool(data.pago)),
                    commit=commit,
                )
        self._persist_split_template(user_id, data.card_id, canon_desc, prop_tpl, data.valor, commit=commit)
        if reload:
            out_rows = []
            for t in created:
                row = self._reload(t.id, user_id)
                if row.shares:
                    row = self._sync_tx_pago_from_shares(row, commit=commit)
                out_rows.append(row)
            return out_rows
        return created

    def update(
        self,
        user_id: UUID,
        tx_id: UUID,
        data: CardTransactionUpdate,
        *,
        commit: bool = True,
        reload: bool = True,
    ) -> CardTransaction:
        tx = self.txs.get_by_id(tx_id, user_id)
        if tx is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
        ensure_period_mutable(self.db, user_id, tx.period_id)
        prev_desc_key = tx.descricao
        propagate_installment_fields = (
            tx.installment_total > 1 and (data.categoria_id is not None or data.descricao is not None)
        )
        installment_group_ids: list[UUID] = []
        if propagate_installment_fields:
            siblings_before = self._installment_siblings(user_id, tx)
            installment_group_ids = [s.id for s in siblings_before] if siblings_before else [tx.id]

        if data.descricao is not None:
            tx.descricao = canonical_card_description(data.descricao)
        if data.valor is not None:
            tx.valor = data.valor
        if data.categoria_id is not None:
            self._ensure_expense_category(user_id, data.categoria_id)
            tx.categoria_id = data.categoria_id
        if data.data is not None:
            tx.data = data.data
        if data.pago is not None:
            tx.pago = data.pago
        if data.from_statement is not None:
            tx.from_statement = data.from_statement
        if data.period_id is not None:
            p = self.periods.get_by_id(data.period_id, user_id)
            if p is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
            ensure_period_mutable(self.db, user_id, data.period_id)
            tx.period_id = data.period_id
        self.txs.update(tx, commit=commit)
        reloaded = self._reload(tx_id, user_id) if reload else tx

        if propagate_installment_fields:
            target_ids = installment_group_ids or [reloaded.id]
            for sibling_id in target_ids:
                sibling = self.txs.get_by_id(sibling_id, user_id)
                if sibling is None:
                    continue
                if sibling.id != reloaded.id and not is_period_mutable(self.db, user_id, sibling.period_id):
                    continue
                changed = False
                if data.descricao is not None and sibling.descricao != reloaded.descricao:
                    sibling.descricao = reloaded.descricao
                    changed = True
                if (
                    data.categoria_id is not None
                    and reloaded.categoria_id is not None
                    and sibling.categoria_id != reloaded.categoria_id
                ):
                    sibling.categoria_id = reloaded.categoria_id
                    changed = True
                if changed:
                    self.txs.update(sibling, commit=commit)

        if data.shares is not None:
            existing_pago = {
                sh.spender_id: bool(sh.pago) for sh in self.shares.list_for_transaction(reloaded.id)
            }
            pairs = normalize_share_template(
                user_id,
                self.spenders,
                data.shares,
                reloaded.valor,
                existing_pago_by_spender=existing_pago,
            )
            # Em compras parceladas, aplicar a divisão também nas próximas parcelas da mesma compra.
            targets = [reloaded]
            if reloaded.installment_total > 1:
                siblings = self._installment_siblings(user_id, reloaded)
                targets = [
                    s
                    for s in siblings
                    if s.installment_number >= reloaded.installment_number
                ]
                if not targets:
                    targets = [reloaded]
            pago_map = {sid: pago for sid, _, pago in pairs}
            for target in targets:
                if target.id != reloaded.id and not is_period_mutable(self.db, user_id, target.period_id):
                    continue
                line_pairs = scale_shares_to_line(pairs, target.valor, reloaded.valor) if pairs else []
                self._replace_shares(
                    target.id,
                    attach_pago(line_pairs, pago_map),
                    commit=commit,
                )
            if reload:
                reloaded = self._reload(tx_id, user_id)
            self._split_tpl.save_from_pairs(
                user_id,
                reloaded.card_id,
                reloaded.descricao,
                [(sid, val) for sid, val, _ in pairs],
                reloaded.valor,
                commit=commit,
            )
            if prev_desc_key != reloaded.descricao:
                self._split_tpl.delete_for_key(user_id, reloaded.card_id, prev_desc_key)
            if pairs:
                reloaded = self._sync_tx_pago_from_shares(reloaded, commit=commit)
        elif data.valor is not None:
            self._validate_existing_shares_match_valor(reloaded)

        if data.pago is not None:
            shares_now = self.shares.list_for_transaction(reloaded.id)
            if shares_now:
                for sh in shares_now:
                    sh.pago = data.pago
                    self.db.add(sh)
                self.db.flush()
                reloaded.pago = data.pago
                reloaded = self.txs.update(reloaded, commit=commit)

        if data.recorrente:
            recurrence_months = data.recurrence_months or 1
            self._replicate_as_recurring(
                user_id=user_id,
                source_tx=reloaded,
                recurrence_months=recurrence_months,
            )

        return reloaded

    def _installment_siblings(self, user_id: UUID, tx: CardTransaction) -> list[CardTransaction]:
        """Parcelas da mesma compra: usa o vínculo explícito (group_id) e cai na heurística só em dados legados."""
        if tx.installment_group_id is not None:
            members = self.txs.list_by_group_id(user_id, tx.installment_group_id)
            if members:
                return members
        if tx.installment_total <= 1:
            return []
        return self.txs.list_by_installment_group(
            user_id,
            tx.card_id,
            tx.descricao,
            tx.data,
            tx.installment_total,
            tx.valor,
        )

    def delete(self, user_id: UUID, tx_id: UUID) -> None:
        tx = self.txs.get_by_id(tx_id, user_id)
        if tx is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
        # Em compra parcelada, excluir todas as parcelas da mesma compra em todos os períodos.
        if tx.installment_total > 1 or tx.installment_group_id is not None:
            siblings = self._installment_siblings(user_id, tx)
            targets = siblings if siblings else [tx]
            period_ids = {s.period_id for s in targets}
            for period_id in period_ids:
                ensure_period_mutable(self.db, user_id, period_id)
            ids = [s.id for s in targets]
            self.txs.delete_by_ids(user_id, ids)
            return

        ensure_period_mutable(self.db, user_id, tx.period_id)
        self.txs.delete(tx)

    def list_card_expenses_for_import(
        self, user_id: UUID, card_id: UUID, period_id: UUID
    ) -> list[CardTransaction]:
        CardService(self.db).get(user_id, card_id)
        p = self.periods.get_by_id(period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        return self.txs.list_by_card_period_for_import(user_id, card_id, period_id)

    def list_card_expenses(self, user_id: UUID, card_id: UUID, period_id: UUID) -> list[CardTransaction]:
        CardService(self.db).get(user_id, card_id)
        p = self.periods.get_by_id(period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        return self.txs.list_by_card_period(user_id, card_id, period_id)

    def get(self, user_id: UUID, tx_id: UUID) -> CardTransaction:
        tx = self.txs.get_by_id(tx_id, user_id)
        if tx is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
        return tx

    def invoice_total(
        self, user_id: UUID, card_id: UUID, period_id: UUID
    ) -> tuple[Decimal, Decimal, int, date | None]:
        """Retorna (total oficial, unpaid_total, unpaid_count, paid_at)."""
        CardService(self.db).get(user_id, card_id)
        p = self.periods.get_by_id(period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        total = Decimal(str(self.txs.sum_statement_official_by_card_period(user_id, card_id, period_id)))
        unpaid_f, unpaid_count, paid_at = self.txs.unpaid_summary_by_card_period(user_id, card_id, period_id)
        return total, Decimal(str(unpaid_f)), unpaid_count, paid_at

    def total_spent_on_card(self, user_id: UUID, card_id: UUID) -> Decimal:
        CardService(self.db).get(user_id, card_id)
        return Decimal(str(self.txs.sum_all_by_card(user_id, card_id)))

    def mark_all_paid_in_period(self, user_id: UUID, card_id: UUID, period_id: UUID) -> int:
        CardService(self.db).get(user_id, card_id)
        p = self.periods.get_by_id(period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        ensure_period_mutable(self.db, user_id, period_id)
        txs = self.txs.list_by_card_period(user_id, card_id, period_id)
        updated = 0
        for tx in txs:
            shares = self.shares.list_for_transaction(tx.id)
            if shares:
                changed = False
                for sh in shares:
                    if not sh.pago:
                        sh.pago = True
                        self.db.add(sh)
                        changed = True
                if changed or not tx.pago:
                    self.db.flush()
                    tx.pago = True
                    self.txs.update(tx, commit=False)
                    updated += 1
            elif not tx.pago:
                tx.pago = True
                self.txs.update(tx, commit=False)
                updated += 1
        self.db.commit()
        DashboardCache.invalidate_user_period(user_id, period_id)
        if updated > 0:
            try:
                from app.services.notification_service import NotificationService

                card = CardService(self.db).get(user_id, card_id)
                NotificationService(self.db).create_event(
                    user_id=user_id,
                    modulo="cartoes",
                    tipo="fatura_paga",
                    severidade="info",
                    titulo="Fatura marcada como paga",
                    subtitulo=f"{card.nome} · {updated} lançamento(s)",
                    link=f"/cartoes/{card_id}",
                    referencia_id=f"{card_id}:{period_id}",
                )
            except Exception:
                logger.exception(
                    "Falha ao notificar fatura paga card_id=%s period_id=%s", card_id, period_id
                )
        return updated

    def set_share_paid(
        self, user_id: UUID, tx_id: UUID, spender_id: UUID, *, pago: bool
    ) -> CardTransaction:
        tx = self.txs.get_by_id(tx_id, user_id)
        if tx is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
        ensure_period_mutable(self.db, user_id, tx.period_id)
        shares = self.shares.list_for_transaction(tx.id)
        target = next((sh for sh in shares if sh.spender_id == spender_id), None)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parte da pessoa não encontrada neste lançamento",
            )
        target.pago = pago
        self.db.add(target)
        self.db.flush()
        self._sync_tx_pago_from_shares(tx, commit=True)
        return self._reload(tx_id, user_id)

    def set_all_shares_paid(self, user_id: UUID, tx_id: UUID, pago: bool) -> CardTransaction:
        tx = self.txs.get_by_id(tx_id, user_id)
        if tx is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
        ensure_period_mutable(self.db, user_id, tx.period_id)
        shares = self.shares.list_for_transaction(tx.id)
        if not shares:
            tx.pago = pago
            self.txs.update(tx, commit=True)
            return self._reload(tx_id, user_id)
        for sh in shares:
            sh.pago = pago
            self.db.add(sh)
        self.db.flush()
        tx.pago = pago
        self.txs.update(tx, commit=True)
        return self._reload(tx_id, user_id)

    def delete_all_transactions_in_card_period(self, user_id: UUID, card_id: UUID, period_id: UUID) -> int:
        """Remove apenas lançamentos do período (parcelas em outros meses permanecem)."""
        CardService(self.db).get(user_id, card_id)
        p = self.periods.get_by_id(period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        ensure_period_mutable(self.db, user_id, period_id)

        txs = self.txs.list_by_card_period_for_import(user_id, card_id, period_id)
        ids = [t.id for t in txs]
        return self.txs.delete_by_ids(user_id, ids)

    def delete_period_and_linked_installments(self, user_id: UUID, card_id: UUID, period_id: UUID) -> int:
        """Compatível com clientes antigos: hoje só apaga o período informado (não apaga parcelas em outros meses)."""
        return self.delete_all_transactions_in_card_period(user_id, card_id, period_id)

    def delete_all_transactions_in_all_card_periods(self, user_id: UUID, card_id: UUID) -> int:
        """Remove todos os lançamentos do cartão em todos os meses/períodos."""
        CardService(self.db).get(user_id, card_id)
        txs = self.txs.list_by_card(user_id, card_id)
        open_period_ids = {
            period_id
            for period_id in {t.period_id for t in txs}
            if is_period_mutable(self.db, user_id, period_id)
        }
        ids = [t.id for t in txs if t.period_id in open_period_ids]
        return self.txs.delete_by_ids(user_id, ids)

    def spenders_summary(self, user_id: UUID, card_id: UUID, period_id: UUID) -> CardSpenderSummaryResponse:
        CardService(self.db).get(user_id, card_id)
        p = self.periods.get_by_id(period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        txs = self.shares.list_transactions_with_shares_for_card_period(user_id, card_id, period_id)
        bucket: dict[tuple[UUID | None, str | None], list[SpenderSummaryLine]] = {}
        totals: dict[tuple[UUID | None, str | None], Decimal] = {}

        def add_line(
            key: tuple[UUID | None, str | None],
            line: SpenderSummaryLine,
            amount: Decimal,
        ) -> None:
            bucket.setdefault(key, []).append(line)
            totals[key] = totals.get(key, Decimal("0")) + amount

        for tx in txs:
            if not tx.shares:
                add_line(
                    (None, None),
                    SpenderSummaryLine(
                        transaction_id=tx.id,
                        descricao=tx.descricao,
                        data=tx.data,
                        valor_parte=tx.valor,
                    ),
                    tx.valor,
                )
                continue
            for sh in tx.shares:
                nome = sh.spender.nome if sh.spender else "?"
                key = (sh.spender_id, nome)
                add_line(
                    key,
                    SpenderSummaryLine(
                        transaction_id=tx.id,
                        descricao=tx.descricao,
                        data=tx.data,
                        valor_parte=sh.valor,
                    ),
                    sh.valor,
                )

        groups: list[SpenderSummaryGroup] = []
        for key, lines in bucket.items():
            sid, nome = key
            groups.append(
                SpenderSummaryGroup(
                    spender_id=sid,
                    spender_nome=nome,
                    total=totals[key],
                    lines=sorted(lines, key=lambda x: (x.data, x.transaction_id)),
                )
            )
        groups.sort(key=lambda g: (0 if g.spender_id is not None else 1, g.spender_nome or ""))

        return CardSpenderSummaryResponse(card_id=card_id, period_id=period_id, groups=groups)
