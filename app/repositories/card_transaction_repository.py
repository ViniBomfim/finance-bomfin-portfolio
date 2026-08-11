from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, selectinload

from app.models.card_transaction import CardTransaction
from app.models.card_transaction_share import CardTransactionShare
from app.models.category import Category
from app.services.dashboard_cache import DashboardCache
from app.services.statement_total_rules import is_statement_payment_description
from app.services.statement_parse_service import (
    _split_itau_attached_parcela,
    extract_parcela_from_description,
)


def _as_local_date(value: date | datetime) -> date:
    """Converte timestamp (UTC/naive-UTC) para o dia civil no fuso local."""
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return dt.astimezone().date()
    return value


def _norm_desc_key(desc: str) -> str:
    base, pa, pt = extract_parcela_from_description(desc)
    if not (pa and pt):
        base, _, _ = _split_itau_attached_parcela(base)
    return base.strip().lower()


def _resolve_tx_installment(desc: str, installment_number: int, installment_total: int) -> tuple[int, int]:
    """Parcela efetiva: metadados com pt>1 têm prioridade; senão extrai da descrição (inclusive colada)."""
    base, pa_from_desc, pt_from_desc = extract_parcela_from_description(desc)
    if not (pa_from_desc and pt_from_desc):
        _, pa_glue, pt_glue = _split_itau_attached_parcela(base)
        if pa_glue and pt_glue:
            pa_from_desc, pt_from_desc = pa_glue, pt_glue
    if installment_total and installment_total > 1:
        return installment_number or 1, installment_total
    if pa_from_desc and pt_from_desc:
        return pa_from_desc, pt_from_desc
    return installment_number or 1, installment_total or 1


def select_installment_group_members(
    rows: list[CardTransaction],
    *,
    descricao: str,
    data_iso: date,
    valor: Decimal,
) -> list[CardTransaction]:
    """Entre linhas do mesmo cartão e ``installment_total``, devolve as parcelas da mesma compra.

    Replica a ideia de ``list_existing_installments``: descrição comparada sem sufixo de parcela;
    valor iguala faturas importadas; data iguala parcelamento manual com valores arredondados por mês.
    """
    want_norm = _norm_desc_key(descricao)
    candidates = [x for x in rows if _norm_desc_key(x.descricao) == want_norm]
    if not candidates:
        return []

    def sort_key(x: CardTransaction) -> int:
        return x.installment_number

    # Caminho antigo: strings idênticas (dados legados já alinhados mês a mês)
    legacy = [x for x in rows if x.descricao == descricao and x.data == data_iso]
    if len(legacy) >= 2:
        return sorted(legacy, key=sort_key)

    strict = [x for x in candidates if x.valor == valor and x.data == data_iso]
    if len(strict) >= 2:
        return sorted(strict, key=sort_key)

    by_valor = [x for x in candidates if x.valor == valor]
    if len(by_valor) >= 2:
        return sorted(by_valor, key=sort_key)

    by_data = [x for x in candidates if x.data == data_iso]
    if len(by_data) >= 2:
        return sorted(by_data, key=sort_key)

    if len(strict) == 1:
        return sorted(strict, key=sort_key)
    if len(by_valor) == 1:
        return sorted(by_valor, key=sort_key)
    if len(by_data) == 1:
        return sorted(by_data, key=sort_key)
    return sorted(legacy, key=sort_key) if legacy else []


class CardTransactionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, tx_id: UUID, user_id: UUID) -> CardTransaction | None:
        stmt = (
            select(CardTransaction)
            .options(
                selectinload(CardTransaction.categoria),
                selectinload(CardTransaction.shares).selectinload(CardTransactionShare.spender),
            )
            .where(CardTransaction.id == tx_id, CardTransaction.user_id == user_id)
        )
        return self.db.execute(stmt).scalars().first()

    def list_by_card_period(self, user_id: UUID, card_id: UUID, period_id: UUID) -> list[CardTransaction]:
        stmt = (
            select(CardTransaction)
            .options(
                selectinload(CardTransaction.categoria),
                selectinload(CardTransaction.shares).selectinload(CardTransactionShare.spender),
            )
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.card_id == card_id,
                CardTransaction.period_id == period_id,
            )
            .order_by(CardTransaction.data.desc(), CardTransaction.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_by_card_period_for_import(
        self, user_id: UUID, card_id: UUID, period_id: UUID
    ) -> list[CardTransaction]:
        """Lista leve para deduplicação/classificação de importação (sem shares)."""
        stmt = (
            select(CardTransaction)
            .options(selectinload(CardTransaction.categoria))
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.card_id == card_id,
                CardTransaction.period_id == period_id,
            )
            .order_by(CardTransaction.data.asc(), CardTransaction.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_by_card(self, user_id: UUID, card_id: UUID) -> list[CardTransaction]:
        stmt = (
            select(CardTransaction)
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.card_id == card_id,
            )
            .order_by(CardTransaction.created_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_installment_in_period(
        self,
        *,
        user_id: UUID,
        card_id: UUID,
        period_id: UUID,
        descricao: str,
        installment_number: int,
        installment_total: int,
    ) -> CardTransaction | None:
        """Mesma parcela X/Y da compra no período (ignora data e valor da linha)."""
        if installment_total <= 1:
            return None
        want_norm = _norm_desc_key(descricao)
        stmt = (
            select(CardTransaction)
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.card_id == card_id,
                CardTransaction.period_id == period_id,
                CardTransaction.installment_number == installment_number,
                CardTransaction.installment_total == installment_total,
            )
            .order_by(CardTransaction.created_at.asc())
        )
        rows = list(self.db.execute(stmt).scalars().all())
        for row in rows:
            if _norm_desc_key(row.descricao) == want_norm:
                return row
        # Fallback: parcela colada na descrição com metadados 1/1 (importação Itaú antiga).
        stmt_all = (
            select(CardTransaction)
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.card_id == card_id,
                CardTransaction.period_id == period_id,
            )
            .order_by(CardTransaction.created_at.asc())
        )
        for row in self.db.execute(stmt_all).scalars().all():
            if _norm_desc_key(row.descricao) != want_norm:
                continue
            pa, pt = _resolve_tx_installment(row.descricao, row.installment_number, row.installment_total)
            if pa == installment_number and pt == installment_total:
                return row
        return None

    def find_matching_for_import(
        self,
        *,
        user_id: UUID,
        card_id: UUID,
        period_id: UUID,
        descricao: str,
        valor: Decimal,
        data_iso: date,
        installment_number: int,
        installment_total: int,
        exclude_ids: set[UUID] | None = None,
    ) -> CardTransaction | None:
        """Busca lançamento já importado no mesmo período para evitar duplicidade em reimport.

        Preferência: mesma data+valor+parcela+descrição.
        Parcelas X/Y (installment_total > 1) usam find_installment_in_period (ignora data/valor).
        À vista (1/1): só casa com a mesma data — desc+valor em data diferente é lançamento novo
        (ex.: NuTag / pedágios recorrentes).
        """
        want_norm = _norm_desc_key(descricao)
        skip = exclude_ids or set()
        stmt = (
            select(CardTransaction)
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.card_id == card_id,
                CardTransaction.period_id == period_id,
                CardTransaction.data == data_iso,
                CardTransaction.valor == valor,
                CardTransaction.installment_number == installment_number,
                CardTransaction.installment_total == installment_total,
            )
            .order_by(CardTransaction.created_at.asc())
        )
        rows = list(self.db.execute(stmt).scalars().all())
        for row in rows:
            if row.id in skip:
                continue
            if _norm_desc_key(row.descricao) == want_norm:
                return row
        if installment_total > 1:
            found = self.find_installment_in_period(
                user_id=user_id,
                card_id=card_id,
                period_id=period_id,
                descricao=descricao,
                installment_number=installment_number,
                installment_total=installment_total,
            )
            if found is not None and found.id not in skip:
                return found
            return None

        # À vista: não casar por desc+valor com data diferente (NuTag e pedágios
        # recorrentes virariam "atualizado" e sumiriam do total).
        return None

    def list_by_period(self, user_id: UUID, period_id: UUID) -> list[CardTransaction]:
        stmt = (
            select(CardTransaction)
            .where(CardTransaction.user_id == user_id, CardTransaction.period_id == period_id)
            .order_by(CardTransaction.created_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def sum_by_card_period(self, user_id: UUID, card_id: UUID, period_id: UUID) -> float:
        stmt = select(func.coalesce(func.sum(CardTransaction.valor), 0)).where(
            CardTransaction.user_id == user_id,
            CardTransaction.card_id == card_id,
            CardTransaction.period_id == period_id,
        )
        return float(self.db.execute(stmt).scalar() or 0)

    def unpaid_summary_by_card_period(
        self, user_id: UUID, card_id: UUID, period_id: UUID
    ) -> tuple[float, int, date | None]:
        """Soma/contagem de não pagos e data de consolidação quando tudo está pago.

        Retorna ``(unpaid_total, unpaid_count, paid_at)``. ``paid_at`` é o dia
        civil local (YYYY-MM-DD) de ``max(updated_at)`` entre lançamentos pagos
        quando ``unpaid_count == 0`` e há lançamentos; senão ``None``.
        """
        base = (
            CardTransaction.user_id == user_id,
            CardTransaction.card_id == card_id,
            CardTransaction.period_id == period_id,
        )
        unpaid_stmt = select(
            func.coalesce(func.sum(CardTransaction.valor), 0),
            func.count(CardTransaction.id),
        ).where(*base, CardTransaction.pago.is_(False))
        unpaid_total, unpaid_count = self.db.execute(unpaid_stmt).one()
        unpaid_total_f = float(unpaid_total or 0)
        unpaid_count_i = int(unpaid_count or 0)

        paid_at: date | None = None
        if unpaid_count_i == 0:
            count_stmt = select(func.count(CardTransaction.id)).where(*base)
            total_count = int(self.db.execute(count_stmt).scalar() or 0)
            if total_count > 0:
                max_updated = self.db.execute(
                    select(func.max(CardTransaction.updated_at)).where(*base, CardTransaction.pago.is_(True))
                ).scalar()
                if max_updated is not None:
                    paid_at = _as_local_date(max_updated)

        return unpaid_total_f, unpaid_count_i, paid_at

    def sum_statement_official_by_card_period(self, user_id: UUID, card_id: UUID, period_id: UUID) -> float:
        """Total oficial da fatura: linhas importadas de fatura, sem pagamentos recebidos."""
        stmt = select(CardTransaction.valor, CardTransaction.descricao).where(
            CardTransaction.user_id == user_id,
            CardTransaction.card_id == card_id,
            CardTransaction.period_id == period_id,
            CardTransaction.from_statement.is_(True),
        )
        rows = self.db.execute(stmt).all()
        total = Decimal("0")
        for valor, descricao in rows:
            if is_statement_payment_description(descricao or ""):
                continue
            total += valor
        return float(total)

    def sum_all_by_card(self, user_id: UUID, card_id: UUID) -> float:
        """Soma de todos os lançamentos do cartão (todas as parcelas e períodos)."""
        stmt = select(func.coalesce(func.sum(CardTransaction.valor), 0)).where(
            CardTransaction.user_id == user_id,
            CardTransaction.card_id == card_id,
        )
        return float(self.db.execute(stmt).scalar() or 0)

    def list_by_installment_group(
        self,
        user_id: UUID,
        card_id: UUID,
        descricao: str,
        data_iso: date,
        installment_total: int,
        valor: Decimal,
    ) -> list[CardTransaction]:
        """Todas as parcelas da mesma compra (descrição normalizada, valor e/ou data como em importação)."""
        if installment_total <= 1:
            return []
        stmt = (
            select(CardTransaction)
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.card_id == card_id,
                CardTransaction.installment_total == installment_total,
            )
            .order_by(CardTransaction.installment_number.asc())
        )
        rows = list(self.db.execute(stmt).scalars().all())
        return select_installment_group_members(rows, descricao=descricao, data_iso=data_iso, valor=valor)

    def list_by_group_id(self, user_id: UUID, group_id: UUID) -> list[CardTransaction]:
        """Todas as parcelas da mesma compra pelo vínculo explícito (installment_group_id)."""
        stmt = (
            select(CardTransaction)
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.installment_group_id == group_id,
            )
            .order_by(CardTransaction.installment_number.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def delete_by_ids(self, user_id: UUID, ids: list[UUID], *, commit: bool = True) -> int:
        if not ids:
            return 0
        period_stmt = (
            select(CardTransaction.period_id)
            .where(CardTransaction.user_id == user_id, CardTransaction.id.in_(ids))
            .distinct()
        )
        period_ids = [row[0] for row in self.db.execute(period_stmt).all()]
        stmt = delete(CardTransaction).where(
            CardTransaction.user_id == user_id,
            CardTransaction.id.in_(ids),
        )
        r = self.db.execute(stmt)
        if commit:
            self.db.commit()
            for period_id in period_ids:
                DashboardCache.invalidate_user_period(user_id, period_id)
        return int(r.rowcount or 0)

    def mark_all_paid_in_period(self, user_id: UUID, card_id: UUID, period_id: UUID) -> int:
        stmt = (
            update(CardTransaction)
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.card_id == card_id,
                CardTransaction.period_id == period_id,
                CardTransaction.pago.is_(False),
            )
            .values(pago=True)
        )
        r = self.db.execute(stmt)
        self.db.commit()
        DashboardCache.invalidate_user_period(user_id, period_id)
        return int(r.rowcount or 0)

    def sum_by_period(self, user_id: UUID, period_id: UUID) -> float:
        stmt = select(func.coalesce(func.sum(CardTransaction.valor), 0)).where(
            CardTransaction.user_id == user_id,
            CardTransaction.period_id == period_id,
        )
        return float(self.db.execute(stmt).scalar() or 0)

    def sum_unpaid_by_period(self, user_id: UUID, period_id: UUID) -> float:
        stmt = select(func.coalesce(func.sum(CardTransaction.valor), 0)).where(
            CardTransaction.user_id == user_id,
            CardTransaction.period_id == period_id,
            CardTransaction.pago.is_(False),
        )
        return float(self.db.execute(stmt).scalar() or 0)

    def aggregates_by_category_period(self, user_id: UUID, period_id: UUID) -> list[tuple[UUID, str, float]]:
        stmt = (
            select(CardTransaction.categoria_id, Category.nome, func.coalesce(func.sum(CardTransaction.valor), 0))
            .join(Category, CardTransaction.categoria_id == Category.id)
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.period_id == period_id,
            )
            .group_by(CardTransaction.categoria_id, Category.nome)
        )
        rows = self.db.execute(stmt).all()
        return [(r[0], r[1], float(r[2] or 0)) for r in rows]

    def create(self, tx: CardTransaction, *, commit: bool = True) -> CardTransaction:
        self.db.add(tx)
        if commit:
            self.db.commit()
            self.db.refresh(tx)
            DashboardCache.invalidate_user_period(tx.user_id, tx.period_id)
        else:
            self.db.flush()
        return tx

    def create_many(self, txs: list[CardTransaction], *, commit: bool = True) -> list[CardTransaction]:
        if not txs:
            return txs
        for t in txs:
            self.db.add(t)
        if commit:
            self.db.commit()
            for t in txs:
                self.db.refresh(t)
            seen: set[tuple[UUID, UUID]] = set()
            for t in txs:
                key = (t.user_id, t.period_id)
                if key not in seen:
                    seen.add(key)
                    DashboardCache.invalidate_user_period(t.user_id, t.period_id)
        else:
            self.db.flush()
        return txs

    def list_existing_installments(
        self,
        *,
        user_id: UUID,
        card_id: UUID,
        descricao: str,
        valor: Decimal,
        data_iso: date,
        installment_total: int,
        period_ids: list[UUID],
        installment_numbers: list[int],
    ) -> list[CardTransaction]:
        """Parcelas já gravadas no mesmo cartão/total; `descricao` comparada pelo nome sem sufixo de parcela.

        Valor e data da linha importada não entram na igualdade (parcelas podem ter valores distintos
        ou datas diferentes entre PDF e CSV).
        """
        _ = data_iso, valor  # mantidos na assinatura por compatibilidade com chamadas existentes
        if not period_ids or not installment_numbers:
            return []
        want_norm = extract_parcela_from_description(descricao)[0].strip().lower()
        stmt = (
            select(CardTransaction)
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.card_id == card_id,
                CardTransaction.installment_total == installment_total,
                CardTransaction.period_id.in_(period_ids),
                CardTransaction.installment_number.in_(installment_numbers),
            )
            .order_by(CardTransaction.installment_number.asc())
        )
        rows = list(self.db.execute(stmt).scalars().all())
        return [
            x
            for x in rows
            if extract_parcela_from_description(x.descricao)[0].strip().lower() == want_norm
        ]

    def find_installment_propagation_source(
        self,
        *,
        user_id: UUID,
        card_id: UUID,
        descricao: str,
        valor: Decimal,
        installment_total: int,
        before_installment_number: int,
    ) -> CardTransaction | None:
        """Parcela anterior da mesma compra (mesmo valor de parcela e total), para herdar categoria/divisão."""
        if installment_total <= 1 or before_installment_number <= 1:
            return None
        want_norm = _norm_desc_key(descricao)
        stmt = (
            select(CardTransaction)
            .options(selectinload(CardTransaction.shares))
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.card_id == card_id,
                CardTransaction.installment_total == installment_total,
                CardTransaction.valor == valor,
                CardTransaction.installment_number < before_installment_number,
            )
            .order_by(CardTransaction.installment_number.desc())
        )
        rows = list(self.db.execute(stmt).scalars().all())
        for x in rows:
            if _norm_desc_key(x.descricao) != want_norm:
                continue
            if x.categoria_id is not None or (x.shares and len(x.shares) > 0):
                return x
        for x in rows:
            if _norm_desc_key(x.descricao) == want_norm:
                return x
        return None

    def list_similar_rows_for_import(
        self,
        *,
        user_id: UUID,
        card_id: UUID,
        descricao: str,
        valor: Decimal,
        data_iso: date,
        installment_total: int,
        period_ids: list[UUID],
    ) -> list[CardTransaction]:
        """Linhas já existentes nos períodos alvo com mesma compra parcelada.

        Compara nome-base + total de parcelas + valor da parcela. O valor é essencial para
        NÃO confundir duas compras diferentes no mesmo estabelecimento com o mesmo número de
        parcelas (ex.: "Loja X 1/2 = 259,50" e "Loja X 2/2 = 600,00"); a data é ignorada porque
        pode variar entre PDF/CSV ou entre meses da mesma compra.
        """
        if not period_ids:
            return []
        want_norm = extract_parcela_from_description(descricao)[0].strip().lower()
        stmt = (
            select(CardTransaction)
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.card_id == card_id,
                CardTransaction.period_id.in_(period_ids),
                CardTransaction.installment_total == installment_total,
                CardTransaction.valor == valor,
            )
            .order_by(CardTransaction.installment_number.asc(), CardTransaction.created_at.asc())
        )
        rows = list(self.db.execute(stmt).scalars().all())
        _ = data_iso
        return [
            x
            for x in rows
            if extract_parcela_from_description(x.descricao)[0].strip().lower() == want_norm
        ]

    def find_matching_single_charge(
        self,
        *,
        user_id: UUID,
        card_id: UUID,
        period_id: UUID,
        descricao: str,
        valor: Decimal,
        data_iso: date,
    ) -> CardTransaction | None:
        """Evita duplicar lançamentos recorrentes simples no mesmo período."""
        want_norm = extract_parcela_from_description(descricao)[0].strip().lower()
        stmt = (
            select(CardTransaction)
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.card_id == card_id,
                CardTransaction.period_id == period_id,
                CardTransaction.valor == valor,
                CardTransaction.data == data_iso,
                CardTransaction.installment_number == 1,
                CardTransaction.installment_total == 1,
            )
            .order_by(CardTransaction.created_at.asc())
        )
        rows = list(self.db.execute(stmt).scalars().all())
        for row in rows:
            if extract_parcela_from_description(row.descricao)[0].strip().lower() == want_norm:
                return row
        return None

    def update(self, tx: CardTransaction, *, commit: bool = True) -> CardTransaction:
        if commit:
            self.db.commit()
            self.db.refresh(tx)
            DashboardCache.invalidate_user_period(tx.user_id, tx.period_id)
        else:
            self.db.flush()
        return tx

    def delete(self, tx: CardTransaction, *, commit: bool = True) -> None:
        user_id = tx.user_id
        period_id = tx.period_id
        self.db.delete(tx)
        if commit:
            self.db.commit()
            DashboardCache.invalidate_user_period(user_id, period_id)
        else:
            self.db.flush()
