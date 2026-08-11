from decimal import Decimal
from uuid import UUID
import unicodedata

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.expenses.enums import ExpenseType
from app.expenses.model import Expense
from app.models.goal import Goal
from app.models.goal_transaction import GoalTransaction
from app.models.income import Income
from app.repositories.category_repository import CategoryRepository
from app.repositories.goal_repository import GoalRepository
from app.repositories.goal_transaction_repository import GoalTransactionRepository
from app.repositories.income_repository import IncomeRepository
from app.repositories.period_repository import PeriodRepository
from app.schemas.goal_schema import GoalCreate, GoalPoolSummaryResponse, GoalProgressResponse, GoalTransactionCreate, GoalUpdate
from app.services.dashboard_cache import DashboardCache
from app.services.period_mutability import ensure_period_mutable


def _normalize_category_name(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return stripped.strip().lower()

class GoalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.goals = GoalRepository(db)
        self.goal_txs = GoalTransactionRepository(db)
        self.categories = CategoryRepository(db)
        self.periods = PeriodRepository(db)
        self.incomes = IncomeRepository(db)

    def create(self, user_id: UUID, data: GoalCreate) -> Goal:
        g = Goal(
            nome=data.nome,
            tipo=data.tipo,
            valor_meta=data.valor_meta,
            valor_atual=data.valor_atual,
            data_inicio=data.data_inicio,
            data_fim=data.data_fim,
            status=data.status,
            user_id=user_id,
        )
        return self.goals.create(g)

    def update(self, user_id: UUID, goal_id: UUID, data: GoalUpdate) -> Goal:
        g = self.goals.get_by_id(goal_id, user_id)
        if g is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
        if data.nome is not None:
            g.nome = data.nome
        if data.tipo is not None:
            g.tipo = data.tipo
        if data.valor_meta is not None:
            g.valor_meta = data.valor_meta
        if data.data_fim is not None:
            g.data_fim = data.data_fim
        if data.status is not None:
            prev_status = g.status
            g.status = data.status
            updated = self.goals.update(g)
            if prev_status != "completed" and data.status == "completed":
                try:
                    from app.services.notification_service import NotificationService, _money

                    NotificationService(self.db).create_event(
                        user_id=user_id,
                        modulo="metas",
                        tipo="meta_concluida",
                        severidade="info",
                        titulo=f'Meta "{updated.nome}" concluída!',
                        subtitulo=f"Objetivo de {_money(updated.valor_meta)} atingido",
                        link=f"/metas/{updated.id}",
                        referencia_id=str(updated.id),
                    )
                except Exception:
                    pass
            return updated
        return self.goals.update(g)

    def delete(self, user_id: UUID, goal_id: UUID) -> None:
        g = self.goals.get_by_id(goal_id, user_id)
        if g is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
        self.goals.delete(g)

    def list_goals(self, user_id: UUID) -> list[Goal]:
        return self.goals.list_by_user(user_id)

    def pool_summary(self, user_id: UUID, period_id: UUID) -> GoalPoolSummaryResponse:
        """Contabiliza o pool de metas do mês: cada competência é fechada em si mesma.

        available = despesas fixas de Metas do mês
                    - depósitos do mês
                    + retiradas que voltaram ao pool
                    - receitas de retirada sem movimentação viva (meta excluída)

        Retirada lançada como receita não volta ao pool: ela sai da conta pelo próprio
        valor da movimentação. Quando a meta é excluída suas movimentações somem, mas a
        receita permanece — daí o termo órfão, que é ignorado se o mês não tem pool algum
        para evitar disponível negativo depois que tudo foi apagado.
        """
        goal_category_ids = [
            cat.id
            for cat in self.categories.list_by_user(user_id, tipo="expense")
            if "meta" in _normalize_category_name(cat.nome)
        ]

        pool_total = Decimal("0")
        if goal_category_ids:
            pool_stmt = select(func.coalesce(func.sum(Expense.valor), 0)).where(
                Expense.user_id == user_id,
                Expense.categoria_id.in_(goal_category_ids),
                Expense.tipo == ExpenseType.FIXED,
                Expense.period_id == period_id,
            )
            pool_total = Decimal(str(self.db.execute(pool_stmt).scalar() or 0))

        deposits = self._movement_total(user_id, period_id, "deposit")
        withdrawals = self._movement_total(user_id, period_id, "withdraw")

        linked_stmt = (
            select(func.coalesce(func.sum(GoalTransaction.valor), 0))
            .select_from(GoalTransaction)
            .join(Income, GoalTransaction.income_id == Income.id)
            .where(
                GoalTransaction.user_id == user_id,
                GoalTransaction.period_id == period_id,
                GoalTransaction.tipo == "withdraw",
            )
        )
        withdrawals_as_income = Decimal(str(self.db.execute(linked_stmt).scalar() or 0))

        meta_income_stmt = select(func.coalesce(func.sum(Income.valor), 0)).where(
            Income.user_id == user_id,
            Income.period_id == period_id,
            Income.origem_meta.is_(True),
        )
        meta_income = Decimal(str(self.db.execute(meta_income_stmt).scalar() or 0))
        orphan_income = max(Decimal("0"), meta_income - withdrawals_as_income)
        if pool_total <= 0:
            orphan_income = Decimal("0")

        withdrawals_to_pool = withdrawals - withdrawals_as_income
        deposited_total = deposits - withdrawals
        available = pool_total - deposits + withdrawals_to_pool - orphan_income
        return GoalPoolSummaryResponse(
            period_id=period_id,
            pool_total=pool_total,
            deposited_total=deposited_total,
            available=available,
        )

    def _movement_total(self, user_id: UUID, period_id: UUID, tipo: str) -> Decimal:
        stmt = select(func.coalesce(func.sum(GoalTransaction.valor), 0)).where(
            GoalTransaction.user_id == user_id,
            GoalTransaction.period_id == period_id,
            GoalTransaction.tipo == tipo,
        )
        return Decimal(str(self.db.execute(stmt).scalar() or 0))

    def get(self, user_id: UUID, goal_id: UUID) -> Goal:
        g = self.goals.get_by_id(goal_id, user_id)
        if g is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
        return g

    def progress(self, user_id: UUID, goal_id: UUID) -> GoalProgressResponse:
        g = self.get(user_id, goal_id)
        pct = float((g.valor_atual / g.valor_meta * Decimal(100))) if g.valor_meta > 0 else 0.0
        return GoalProgressResponse(
            goal_id=g.id,
            tipo=g.tipo,
            valor_meta=g.valor_meta,
            valor_atual=g.valor_atual,
            progress_percent=round(pct, 2),
        )

    def add_transaction(self, user_id: UUID, goal_id: UUID, data: GoalTransactionCreate) -> GoalTransaction:
        g = self.get(user_id, goal_id)
        if data.tipo == "withdraw" and g.valor_atual < data.valor:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient balance in goal")

        period = self.periods.get_by_month_year(user_id, data.data.month, data.data.year)
        if period is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Período não encontrado para a data informada.",
            )

        if data.tipo == "deposit":
            available = self.pool_summary(user_id, period.id).available
            if data.valor > available:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Disponível insuficiente na competência {period.mes:02d}/{period.ano}: "
                        f"{available}."
                    ),
                )

        income_id: UUID | None = None
        income_period_id: UUID | None = None

        if data.tipo == "withdraw" and data.launch_as_income:
            assert data.categoria_id is not None
            ensure_period_mutable(self.db, user_id, period.id)

            categoria = self.categories.get_by_id(data.categoria_id, user_id)
            if categoria is None or categoria.tipo != "income":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid income category")

            descricao = data.descricao.strip() if data.descricao and data.descricao.strip() else f"Retirada: {g.nome}"
            income = Income(
                descricao=descricao,
                valor=data.valor,
                data=data.data,
                recorrente=False,
                origem_meta=True,
                period_id=period.id,
                categoria_id=data.categoria_id,
                user_id=user_id,
            )
            self.db.add(income)
            self.db.flush()
            income_id = income.id
            income_period_id = period.id

        if data.tipo == "deposit":
            g.valor_atual += data.valor
        else:
            g.valor_atual -= data.valor

        tx = GoalTransaction(
            tipo=data.tipo,
            valor=data.valor,
            descricao=data.descricao,
            data=data.data,
            goal_id=g.id,
            user_id=user_id,
            income_id=income_id,
            period_id=period.id,
        )
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(g)
        self.db.refresh(tx)
        DashboardCache.invalidate_user(user_id)
        if income_period_id is not None:
            DashboardCache.invalidate_user_period(user_id, income_period_id)

        try:
            from app.services.notification_service import NotificationService, _money

            notif = NotificationService(self.db)
            if data.tipo == "deposit":
                notif.create_event(
                    user_id=user_id,
                    modulo="metas",
                    tipo="deposito_registrado",
                    severidade="info",
                    titulo=f'Depósito em "{g.nome}"',
                    subtitulo=f"{_money(data.valor)} · saldo {_money(g.valor_atual)}",
                    link=f"/metas/{g.id}",
                    referencia_id=str(tx.id),
                )
                if g.valor_atual >= g.valor_meta and g.status == "active":
                    g.status = "completed"
                    self.db.add(g)
                    self.db.commit()
                    self.db.refresh(g)
                    notif.create_event(
                        user_id=user_id,
                        modulo="metas",
                        tipo="meta_concluida",
                        severidade="info",
                        titulo=f'Meta "{g.nome}" concluída!',
                        subtitulo=f"Objetivo de {_money(g.valor_meta)} atingido",
                        link=f"/metas/{g.id}",
                        referencia_id=str(g.id),
                    )
        except Exception:
            pass
        return tx

    def list_transactions(self, user_id: UUID, goal_id: UUID) -> list[GoalTransaction]:
        self.get(user_id, goal_id)
        return self.goal_txs.list_by_goal(user_id, goal_id)

    def delete_transaction(self, user_id: UUID, goal_id: UUID, tx_id: UUID) -> None:
        g = self.get(user_id, goal_id)
        tx = self.goal_txs.get_by_id(tx_id, user_id)
        if tx is None or tx.goal_id != goal_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

        income_period_id: UUID | None = None
        if tx.income_id is not None:
            income = self.incomes.get_by_id(tx.income_id, user_id)
            if income is not None:
                income_period_id = income.period_id
                self.db.delete(income)

        if tx.tipo == "deposit":
            if g.valor_atual < tx.valor:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot revert deposit: insufficient balance in goal",
                )
            g.valor_atual -= tx.valor
        else:
            g.valor_atual += tx.valor

        self.db.delete(tx)
        self.db.commit()
        self.db.refresh(g)
        DashboardCache.invalidate_user(user_id)
        if income_period_id is not None:
            DashboardCache.invalidate_user_period(user_id, income_period_id)
