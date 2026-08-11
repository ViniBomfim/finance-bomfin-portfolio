from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.expenses.enums import ExpenseType
from app.expenses.model import Expense
from app.models.notification import Notification
from app.models.period import Period
from app.models.trip_expense import TripExpense
from app.models.user import User
from app.repositories.card_repository import CardRepository
from app.repositories.card_transaction_repository import CardTransactionRepository
from app.repositories.debtor_repository import DebtorRepository
from app.repositories.goal_repository import GoalRepository
from app.repositories.notification_repository import MODULES, NotificationRepository
from app.repositories.period_repository import PeriodRepository
from app.schemas.notification_schema import (
    NotificationGenerateResponse,
    NotificationGrupos,
    NotificationListResponse,
    NotificationResponse,
)
from app.trips.enums import TripStatus
from app.trips.repository import TripRepository

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
MORNING_HOUR = 8

# Tipos de cartão recriados a cada geração; eventos como "fatura_paga" ficam de fora.
CARD_GENERATED_TYPES = (
    "fatura_vencida",
    "fatura_vencendo_urgente",
    "fatura_vencendo_atencao",
    "fatura_fechou",
)


def _money(value: Decimal | float | int) -> str:
    amount = Decimal(str(value)).quantize(CENT)
    formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def _diff_dias(data_inicio: date, data_fim: date) -> int:
    return (data_fim - data_inicio).days


def _effective_day_in_month(day: int, year: int, month: int) -> int:
    safe_day = min(max(day, 1), 31)
    last_day = calendar.monthrange(year, month)[1]
    return min(safe_day, last_day)


def _days_until_next_day(day: int, today: date | None = None) -> int:
    """Days until the next occurrence of a day-of-month (inclusive of today = 0)."""
    now = today or date.today()
    safe_day = min(max(day, 1), 31)
    effective = _effective_day_in_month(safe_day, now.year, now.month)
    if now.day < effective:
        return effective - now.day
    if now.day == effective:
        return 0
    days_left = calendar.monthrange(now.year, now.month)[1] - now.day
    next_month = 1 if now.month == 12 else now.month + 1
    next_year = now.year + 1 if now.month == 12 else now.year
    next_effective = _effective_day_in_month(safe_day, next_year, next_month)
    return days_left + next_effective


def _days_since_last_day(day: int, today: date | None = None) -> int:
    """Days since the most recent occurrence of a day-of-month (0 if today is that day)."""
    now = today or date.today()
    safe_day = min(max(day, 1), 31)
    effective = _effective_day_in_month(safe_day, now.year, now.month)
    if now.day >= effective:
        return now.day - effective
    prev_month = 12 if now.month == 1 else now.month - 1
    prev_year = now.year - 1 if now.month == 1 else now.year
    prev_effective = _effective_day_in_month(safe_day, prev_year, prev_month)
    return (now - date(prev_year, prev_month, prev_effective)).days


def _to_response(row: Notification) -> NotificationResponse:
    return NotificationResponse.model_validate(row)


def _group(rows: list[Notification]) -> NotificationListResponse:
    grupos = NotificationGrupos()
    for row in rows:
        item = _to_response(row)
        bucket = getattr(grupos, row.modulo, None)
        if isinstance(bucket, list):
            bucket.append(item)
    total = sum(len(getattr(grupos, m)) for m in MODULES)
    return NotificationListResponse(total=total, grupos=grupos)


class NotificationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = NotificationRepository(db)

    def list_unread(self, user_id: UUID) -> NotificationListResponse:
        return _group(self.repo.list_unread(user_id))

    def list_historico(self, user_id: UUID) -> NotificationListResponse:
        return _group(self.repo.list_read(user_id, per_module=50))

    def mark_read(self, user_id: UUID, notification_id: UUID) -> NotificationResponse:
        row = self.repo.get_by_id(notification_id, user_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notificação não encontrada")
        if not row.lida:
            row = self.repo.mark_read(row)
        return _to_response(row)

    def mark_all_read(self, user_id: UUID) -> int:
        return self.repo.mark_all_read(user_id)

    def limpar_historico_antigo(self, user_id: UUID | None = None, *, days: int = 90) -> int:
        return self.repo.delete_old_read(days=days, user_id=user_id)

    @staticmethod
    def _is_generation_due(user: User) -> bool:
        """True if generation should run now (once per local day after MORNING_HOUR)."""
        last = user.notifications_generated_at
        if last is None:
            return True
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        last_local = last.astimezone()
        now_local = datetime.now().astimezone()
        if last_local.date() >= now_local.date():
            return False
        return now_local.hour >= MORNING_HOUR

    def gerar_notificacoes(self, user_id: UUID, *, force: bool = False) -> NotificationGenerateResponse:
        user = self.db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
        if not force and not self._is_generation_due(user):
            return NotificationGenerateResponse(created=0, cleaned=0, ran=False)

        created = 0
        created += self._verificar_cartoes(user_id)
        created += self._verificar_devedores(user_id)
        created += self._verificar_metas(user_id)
        created += self._verificar_viagens(user_id)
        created += self._verificar_gastos_fixos(user_id)
        cleaned = self.limpar_historico_antigo(user_id)
        user.notifications_generated_at = datetime.now(timezone.utc)
        self.db.add(user)
        self.db.commit()
        return NotificationGenerateResponse(created=created, cleaned=cleaned, ran=True)

    def create_event(
        self,
        *,
        user_id: UUID,
        modulo: str,
        tipo: str,
        severidade: str,
        titulo: str,
        subtitulo: str,
        link: str,
        referencia_id: str,
        lida: bool = False,
    ) -> Notification | None:
        """Create an event notification; failures are logged and ignored."""
        try:
            if not lida and self.repo.exists_unread(user_id, tipo, referencia_id):
                return None
            row = Notification(
                user_id=user_id,
                modulo=modulo,
                tipo=tipo,
                severidade=severidade,
                titulo=titulo,
                subtitulo=subtitulo,
                link=link,
                referencia_id=referencia_id,
                lida=lida,
                lida_em=datetime.now(timezone.utc) if lida else None,
            )
            return self.repo.create(row, commit=True)
        except Exception:
            logger.exception("Falha ao criar notificação de evento tipo=%s", tipo)
            try:
                self.db.rollback()
            except Exception:
                pass
            return None

    def _upsert_notificacao(
        self,
        *,
        user_id: UUID,
        modulo: str,
        tipo: str,
        severidade: str,
        titulo: str,
        subtitulo: str,
        link: str,
        referencia_id: str,
    ) -> bool:
        """Cria a notificação ou atualiza a não lida existente. True quando cria."""
        existing = self.repo.get_unread(user_id, tipo, referencia_id)
        if existing is not None:
            self.repo.update_content(
                existing,
                severidade=severidade,
                titulo=titulo,
                subtitulo=subtitulo,
                link=link,
                commit=False,
            )
            return False
        self.repo.create(
            Notification(
                user_id=user_id,
                modulo=modulo,
                tipo=tipo,
                severidade=severidade,
                titulo=titulo,
                subtitulo=subtitulo,
                link=link,
                referencia_id=referencia_id,
                lida=False,
            ),
            commit=False,
        )
        return True

    def _current_period(self, user_id: UUID) -> Period | None:
        """Período do mês corrente; se não existir, o próximo aberto à frente."""
        periods = PeriodRepository(self.db).list_by_user(user_id)
        if not periods:
            return None
        today = date.today()
        current = next(
            (p for p in periods if p.ano == today.year and p.mes == today.month),
            None,
        )
        if current is not None:
            return current
        open_ones = [p for p in periods if p.status == "open"]
        if not open_ones:
            return None
        ahead = [p for p in open_ones if (p.ano, p.mes) > (today.year, today.month)]
        if ahead:
            ahead.sort(key=lambda p: (p.ano, p.mes))
            return ahead[0]
        open_ones.sort(key=lambda p: (p.ano, p.mes), reverse=True)
        return open_ones[0]

    def _verificar_cartoes(self, user_id: UUID) -> int:
        created = 0
        cards = CardRepository(self.db).list_by_user(user_id)
        period = self._current_period(user_id)
        tx_repo = CardTransactionRepository(self.db)
        today = date.today()
        emitidas: set[tuple[str, str]] = set()

        for card in cards:
            unpaid = Decimal("0")
            unpaid_count = 0
            if period is not None:
                unpaid_f, unpaid_count, _ = tx_repo.unpaid_summary_by_card_period(
                    user_id, card.id, period.id
                )
                unpaid = Decimal(str(unpaid_f)).quantize(CENT)

            dias_vencer = _days_until_next_day(card.vencimento, today)
            dias_atraso = _days_since_last_day(card.vencimento, today)
            ref = str(card.id)
            banco = card.banco.strip() if card.banco else ""
            nome_banco = f"{card.nome} ({banco})" if banco else card.nome

            # Fatura já venceu e ainda há valor não pago
            if dias_atraso > 0 and unpaid_count > 0:
                titulo = (
                    "Fatura vencida há 1 dia"
                    if dias_atraso == 1
                    else f"Fatura vencida há {dias_atraso} dias"
                )
                emitidas.add(("fatura_vencida", ref))
                if self._upsert_notificacao(
                    user_id=user_id,
                    modulo="cartoes",
                    tipo="fatura_vencida",
                    severidade="urgente",
                    titulo=titulo,
                    subtitulo=f"{nome_banco} · {_money(unpaid)} pendente",
                    link=f"/cartoes/{card.id}",
                    referencia_id=ref,
                ):
                    created += 1
            elif 0 <= dias_vencer <= 3 and unpaid_count > 0:
                titulo = (
                    "Fatura vence hoje"
                    if dias_vencer == 0
                    else f"Fatura vence em {dias_vencer} dia(s)"
                )
                emitidas.add(("fatura_vencendo_urgente", ref))
                if self._upsert_notificacao(
                    user_id=user_id,
                    modulo="cartoes",
                    tipo="fatura_vencendo_urgente",
                    severidade="urgente",
                    titulo=titulo,
                    subtitulo=f"{nome_banco} · {_money(unpaid)} pendente",
                    link=f"/cartoes/{card.id}",
                    referencia_id=ref,
                ):
                    created += 1
            elif dias_vencer <= 7 and unpaid_count > 0:
                emitidas.add(("fatura_vencendo_atencao", ref))
                if self._upsert_notificacao(
                    user_id=user_id,
                    modulo="cartoes",
                    tipo="fatura_vencendo_atencao",
                    severidade="atencao",
                    titulo=f"Fatura vence em {dias_vencer} dias",
                    subtitulo=f"{card.nome} · {_money(unpaid)} acumulado",
                    link=f"/cartoes/{card.id}",
                    referencia_id=ref,
                ):
                    created += 1

            dias_fecha = _days_until_next_day(card.fechamento, today)
            if dias_fecha == 0 and unpaid_count > 0:
                emitidas.add(("fatura_fechou", ref))
                if self._upsert_notificacao(
                    user_id=user_id,
                    modulo="cartoes",
                    tipo="fatura_fechou",
                    severidade="info",
                    titulo="Fatura fechou hoje",
                    subtitulo=f"{nome_banco} · {_money(unpaid)} no ciclo",
                    link=f"/cartoes/{card.id}",
                    referencia_id=ref,
                ):
                    created += 1

        self.repo.delete_unread_stale(user_id, CARD_GENERATED_TYPES, emitidas, commit=False)
        return created

    def _verificar_devedores(self, user_id: UUID) -> int:
        created = 0
        loans = DebtorRepository(self.db).list_loans_by_user(user_id)
        today = date.today()
        for loan in loans:
            valor_pago = sum((p.valor_pago for p in loan.pagamentos), start=Decimal("0")).quantize(CENT)
            restante = (loan.valor_emprestado - valor_pago).quantize(CENT)
            if restante <= 0:
                continue
            ultimo = max((p.data_pagamento for p in loan.pagamentos), default=None)
            base = ultimo or loan.data_emprestimo
            dias = max(0, _diff_dias(base, today))
            ref = str(loan.id)
            if dias > 60:
                if self._upsert_notificacao(
                    user_id=user_id,
                    modulo="devedores",
                    tipo="devedor_muito_atrasado",
                    severidade="urgente",
                    titulo=f"{loan.devedor_nome} sem pagamento há {dias} dias",
                    subtitulo=f"{_money(restante)} pendente",
                    link="/devedores",
                    referencia_id=ref,
                ):
                    created += 1
            elif dias > 30:
                if self._upsert_notificacao(
                    user_id=user_id,
                    modulo="devedores",
                    tipo="devedor_atrasado",
                    severidade="atencao",
                    titulo=f"{loan.devedor_nome} sem pagamento há {dias} dias",
                    subtitulo=f"{_money(restante)} pendente",
                    link="/devedores",
                    referencia_id=ref,
                ):
                    created += 1
        return created

    def _verificar_metas(self, user_id: UUID) -> int:
        created = 0
        goals = GoalRepository(self.db).list_by_user(user_id)
        today = date.today()
        for goal in goals:
            if goal.status != "active":
                continue
            if goal.data_fim is None:
                continue
            dias = _diff_dias(today, goal.data_fim)
            if dias < 0 or dias > 7:
                continue
            progresso = float((goal.valor_atual / goal.valor_meta) * 100) if goal.valor_meta else 0.0
            if progresso >= 100:
                continue
            falta = (goal.valor_meta - goal.valor_atual).quantize(CENT)
            sev = "urgente" if dias <= 3 else "atencao"
            if self._upsert_notificacao(
                user_id=user_id,
                modulo="metas",
                tipo="meta_vencendo",
                severidade=sev,
                titulo=f'Meta "{goal.nome}" vence em {dias} dia(s)' if dias else f'Meta "{goal.nome}" vence hoje',
                subtitulo=f"{progresso:.0f}% concluído · faltam {_money(falta)}",
                link=f"/metas/{goal.id}",
                referencia_id=str(goal.id),
            ):
                created += 1
        return created

    def _verificar_viagens(self, user_id: UUID) -> int:
        created = 0
        trips = TripRepository(self.db).list_by_user(user_id)
        today = date.today()
        for trip in trips:
            if trip.status == TripStatus.CLOSED.value or trip.status == "closed":
                continue
            expenses = (
                self.db.execute(select(TripExpense).where(TripExpense.trip_id == trip.id)).scalars().all()
            )
            total_gasto = sum((e.valor_base for e in expenses), Decimal("0")).quantize(CENT)
            orcamento = trip.orcamento_total
            ref = str(trip.id)
            if orcamento is not None and orcamento > 0:
                pct = float((total_gasto / orcamento) * 100)
                if pct > 100:
                    if self._upsert_notificacao(
                        user_id=user_id,
                        modulo="viagens",
                        tipo="viagem_orcamento_ultrapassado",
                        severidade="urgente",
                        titulo="Orçamento ultrapassado!",
                        subtitulo=f"{trip.nome} · {_money(total_gasto)} de {_money(orcamento)} ({pct:.0f}%)",
                        link=f"/viagens/{trip.id}",
                        referencia_id=ref,
                    ):
                        created += 1
                elif pct > 80:
                    if self._upsert_notificacao(
                        user_id=user_id,
                        modulo="viagens",
                        tipo="viagem_orcamento_alto",
                        severidade="atencao",
                        titulo="Orçamento quase no limite",
                        subtitulo=f"{trip.nome} · {pct:.0f}% usado",
                        link=f"/viagens/{trip.id}",
                        referencia_id=ref,
                    ):
                        created += 1

            if trip.data_inicio is not None:
                dias_inicio = _diff_dias(today, trip.data_inicio)
                if 0 < dias_inicio <= 7:
                    destino = trip.destino or "—"
                    if self._upsert_notificacao(
                        user_id=user_id,
                        modulo="viagens",
                        tipo="viagem_iniciando",
                        severidade="info",
                        titulo=f"Viagem começa em {dias_inicio} dias",
                        subtitulo=f"{trip.nome} · {destino}",
                        link=f"/viagens/{trip.id}",
                        referencia_id=ref,
                    ):
                        created += 1
        return created

    def _verificar_gastos_fixos(self, user_id: UUID) -> int:
        created = 0
        period = self._current_period(user_id)
        if period is None:
            return 0
        today = date.today()
        stmt = (
            select(Expense)
            .options(selectinload(Expense.categoria))
            .where(
                Expense.user_id == user_id,
                Expense.period_id == period.id,
                Expense.tipo == ExpenseType.FIXED,
                Expense.pago.is_(False),
            )
        )
        expenses = list(self.db.execute(stmt).scalars().all())
        for expense in expenses:
            dias = _diff_dias(today, expense.data)
            if dias < 0 or dias > 3:
                continue
            cat = expense.categoria.nome if expense.categoria else "—"
            sev = "urgente" if dias == 0 else "atencao"
            titulo = (
                "Gasto fixo vence hoje"
                if dias == 0
                else f"Gasto fixo vence em {dias} dia(s)"
            )
            if self._upsert_notificacao(
                user_id=user_id,
                modulo="gastos_fixos",
                tipo="gasto_fixo_vencendo",
                severidade=sev,
                titulo=titulo,
                subtitulo=f"{expense.descricao} · {_money(expense.valor)} · {cat}",
                link="/gastos-fixos",
                referencia_id=str(expense.id),
            ):
                created += 1
        return created
