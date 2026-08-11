from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.budget import Budget
from app.repositories.budget_repository import BudgetRepository
from app.repositories.card_transaction_repository import CardTransactionRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.expense_repository import ExpenseRepository
from app.repositories.period_repository import PeriodRepository
from app.schemas.budget_schema import BudgetCompareRow, BudgetCreate, BudgetUpdate
from app.services.period_mutability import ensure_period_mutable


class BudgetService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.budgets = BudgetRepository(db)
        self.periods = PeriodRepository(db)
        self.categories = CategoryRepository(db)
        self.expenses = ExpenseRepository(db)
        self.card_txs = CardTransactionRepository(db)

    def create(self, user_id: UUID, data: BudgetCreate) -> Budget:
        p = self.periods.get_by_id(data.period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        c = self.categories.get_by_id(data.categoria_id, user_id)
        if c is None or c.tipo != "expense":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid expense category")
        existing = self.budgets.get_by_category_period(user_id, data.categoria_id, data.period_id)
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Budget already exists for category/period")
        ensure_period_mutable(self.db, user_id, data.period_id)
        b = Budget(valor=data.valor, categoria_id=data.categoria_id, period_id=data.period_id, user_id=user_id)
        return self.budgets.create(b)

    def update(self, user_id: UUID, budget_id: UUID, data: BudgetUpdate) -> Budget:
        b = self.budgets.get_by_id(budget_id, user_id)
        if b is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
        ensure_period_mutable(self.db, user_id, b.period_id)
        if data.valor is not None:
            b.valor = data.valor
        return self.budgets.update(b)

    def delete(self, user_id: UUID, budget_id: UUID) -> None:
        b = self.budgets.get_by_id(budget_id, user_id)
        if b is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
        ensure_period_mutable(self.db, user_id, b.period_id)
        self.budgets.delete(b)

    def get(self, user_id: UUID, budget_id: UUID) -> Budget:
        b = self.budgets.get_by_id(budget_id, user_id)
        if b is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
        return b

    def list_by_period(self, user_id: UUID, period_id: UUID) -> list[Budget]:
        p = self.periods.get_by_id(period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        return self.budgets.list_by_period(user_id, period_id)

    def compare(self, user_id: UUID, period_id: UUID) -> list[BudgetCompareRow]:
        p = self.periods.get_by_id(period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        budgets = self.budgets.list_by_period(user_id, period_id)
        actual_by_cat: dict[UUID, Decimal] = {}
        for cid, name, amt in self.expenses.aggregates_by_category_period(user_id, period_id):
            actual_by_cat[cid] = Decimal(str(amt))
        for cid, name, amt in self.card_txs.aggregates_by_category_period(user_id, period_id):
            d = Decimal(str(amt))
            if cid in actual_by_cat:
                actual_by_cat[cid] += d
            else:
                actual_by_cat[cid] = d
        rows: list[BudgetCompareRow] = []
        for b in budgets:
            cat = self.categories.get_by_id(b.categoria_id, user_id)
            nome = cat.nome if cat else "?"
            real = actual_by_cat.get(b.categoria_id, Decimal("0"))
            planejado = b.valor
            rows.append(
                BudgetCompareRow(
                    categoria_id=b.categoria_id,
                    categoria_nome=nome,
                    planejado=planejado,
                    realizado=real,
                    diferenca=planejado - real,
                )
            )
        return rows

    def copy_from_previous_month(self, user_id: UUID, target_period_id: UUID) -> list[Budget]:
        """Copia orçamentos do mês civil anterior para o período alvo (só categorias ainda sem orçamento)."""
        target = self.periods.get_by_id(target_period_id, user_id)
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        ensure_period_mutable(self.db, user_id, target_period_id)

        previous = self.periods.get_previous_calendar_month(user_id, target.mes, target.ano)
        if previous is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não há período cadastrado para o mês anterior.",
            )

        source_rows = self.budgets.list_by_period(user_id, previous.id)
        created: list[Budget] = []
        for src in source_rows:
            if self.budgets.get_by_category_period(user_id, src.categoria_id, target_period_id) is not None:
                continue
            b = Budget(
                valor=src.valor,
                categoria_id=src.categoria_id,
                period_id=target_period_id,
                user_id=user_id,
            )
            created.append(self.budgets.create(b))
        return created

    def replicate_budgets_between_years(self, user_id: UUID, from_ano: int, to_ano: int) -> list[Budget]:
        """Para cada mês, copia orçamentos do ano de origem para o de destino (sem sobrescrever)."""
        if from_ano == to_ano:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Os anos de origem e destino devem ser diferentes",
            )
        created: list[Budget] = []
        for mes in range(1, 13):
            src = self.periods.get_by_month_year(user_id, mes, from_ano)
            tgt = self.periods.get_by_month_year(user_id, mes, to_ano)
            if src is None or tgt is None:
                continue
            if tgt.status != "open":
                continue
            for b in self.budgets.list_by_period(user_id, src.id):
                if self.budgets.get_by_category_period(user_id, b.categoria_id, tgt.id) is not None:
                    continue
                nb = Budget(
                    valor=b.valor,
                    categoria_id=b.categoria_id,
                    period_id=tgt.id,
                    user_id=user_id,
                )
                created.append(self.budgets.create(nb))
        return created
