from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.expenses.enums import ExpenseType
from app.expenses.model import Expense
from app.models.category import Category
from app.models.expense_share import ExpenseShare
from app.services.dashboard_cache import DashboardCache


class ExpenseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, expense_id: UUID, user_id: UUID) -> Expense | None:
        stmt = (
            select(Expense)
            .options(
                selectinload(Expense.categoria),
                selectinload(Expense.shares).selectinload(ExpenseShare.spender),
            )
            .where(Expense.id == expense_id, Expense.user_id == user_id)
        )
        e = self.db.execute(stmt).scalar_one_or_none()
        if e is None:
            return None
        return e

    def list_by_period(self, user_id: UUID, period_id: UUID) -> list[Expense]:
        stmt = (
            select(Expense)
            .options(
                selectinload(Expense.categoria),
                selectinload(Expense.shares).selectinload(ExpenseShare.spender),
            )
            .where(Expense.user_id == user_id, Expense.period_id == period_id)
            .order_by(Expense.data)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_fixed_by_descricao_categoria_period(
        self,
        user_id: UUID,
        period_id: UUID,
        categoria_id: UUID,
        descricao: str,
    ) -> Expense | None:
        stmt = select(Expense).where(
            Expense.user_id == user_id,
            Expense.period_id == period_id,
            Expense.categoria_id == categoria_id,
            Expense.descricao == descricao,
            Expense.tipo == ExpenseType.FIXED,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_fixed_by_period(self, user_id: UUID, period_id: UUID) -> list[Expense]:
        stmt = (
            select(Expense)
            .options(
                selectinload(Expense.categoria),
                selectinload(Expense.shares).selectinload(ExpenseShare.spender),
            )
            .where(
                Expense.user_id == user_id,
                Expense.period_id == period_id,
                Expense.tipo == ExpenseType.FIXED,
            )
            .order_by(Expense.data.desc(), Expense.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_by_category(self, user_id: UUID, categoria_id: UUID) -> list[Expense]:
        stmt = (
            select(Expense)
            .options(
                selectinload(Expense.categoria),
                selectinload(Expense.shares).selectinload(ExpenseShare.spender),
            )
            .where(Expense.user_id == user_id, Expense.categoria_id == categoria_id)
            .order_by(Expense.data.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def sum_by_period(self, user_id: UUID, period_id: UUID) -> float:
        stmt = select(func.coalesce(func.sum(Expense.valor), 0)).where(
            Expense.user_id == user_id,
            Expense.period_id == period_id,
        )
        return float(self.db.execute(stmt).scalar() or 0)

    def sum_unpaid_by_period(self, user_id: UUID, period_id: UUID) -> float:
        stmt = select(func.coalesce(func.sum(Expense.valor), 0)).where(
            Expense.user_id == user_id,
            Expense.period_id == period_id,
            Expense.pago.is_(False),
        )
        return float(self.db.execute(stmt).scalar() or 0)

    def sum_by_category_period(self, user_id: UUID, period_id: UUID, categoria_id: UUID) -> float:
        stmt = select(func.coalesce(func.sum(Expense.valor), 0)).where(
            Expense.user_id == user_id,
            Expense.period_id == period_id,
            Expense.categoria_id == categoria_id,
        )
        return float(self.db.execute(stmt).scalar() or 0)

    def aggregates_by_category_period(self, user_id: UUID, period_id: UUID) -> list[tuple[UUID, str, float]]:
        stmt = (
            select(Expense.categoria_id, Category.nome, func.coalesce(func.sum(Expense.valor), 0))
            .join(Category, Expense.categoria_id == Category.id)
            .where(Expense.user_id == user_id, Expense.period_id == period_id)
            .group_by(Expense.categoria_id, Category.nome)
        )
        rows = self.db.execute(stmt).all()
        return [(r[0], r[1], float(r[2] or 0)) for r in rows]

    def aggregates_fixed_by_category_period(self, user_id: UUID, period_id: UUID) -> list[tuple[UUID, str, float]]:
        stmt = (
            select(Expense.categoria_id, Category.nome, func.coalesce(func.sum(Expense.valor), 0))
            .join(Category, Expense.categoria_id == Category.id)
            .where(
                Expense.user_id == user_id,
                Expense.period_id == period_id,
                Expense.tipo == ExpenseType.FIXED,
            )
            .group_by(Expense.categoria_id, Category.nome)
        )
        rows = self.db.execute(stmt).all()
        return [(r[0], r[1], float(r[2] or 0)) for r in rows]

    def create(self, expense: Expense) -> Expense:
        self.db.add(expense)
        self.db.commit()
        self.db.refresh(expense)
        DashboardCache.invalidate_user_period(expense.user_id, expense.period_id)
        return expense

    def update(self, expense: Expense) -> Expense:
        self.db.commit()
        self.db.refresh(expense)
        DashboardCache.invalidate_user_period(expense.user_id, expense.period_id)
        return expense

    def delete(self, expense: Expense) -> None:
        user_id = expense.user_id
        period_id = expense.period_id
        self.db.delete(expense)
        self.db.commit()
        DashboardCache.invalidate_user_period(user_id, period_id)
