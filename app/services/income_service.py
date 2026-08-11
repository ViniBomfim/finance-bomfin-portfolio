from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.goal_transaction import GoalTransaction
from app.models.income import Income
from app.repositories.category_repository import CategoryRepository
from app.repositories.income_repository import IncomeRepository
from app.repositories.period_repository import PeriodRepository
from app.schemas.income_schema import IncomeCreate, IncomeUpdate
from app.services.date_utils import date_in_month
from app.services.period_mutability import ensure_period_mutable


class IncomeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.incomes = IncomeRepository(db)
        self.periods = PeriodRepository(db)
        self.categories = CategoryRepository(db)

    def _validate_refs(self, user_id: UUID, period_id: UUID, categoria_id: UUID) -> None:
        p = self.periods.get_by_id(period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        c = self.categories.get_by_id(categoria_id, user_id)
        if c is None or c.tipo != "income":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid income category")
        ensure_period_mutable(self.db, user_id, period_id)

    def create(self, user_id: UUID, data: IncomeCreate) -> list[Income]:
        self._validate_refs(user_id, data.period_id, data.categoria_id)
        base = Income(
            descricao=data.descricao,
            valor=data.valor,
            data=data.data,
            recorrente=data.recorrente,
            period_id=data.period_id,
            categoria_id=data.categoria_id,
            user_id=user_id,
        )
        self.incomes.create(base)
        created: list[Income] = [base]
        if data.recorrente:
            period = self.periods.get_by_id(data.period_id, user_id)
            assert period is not None
            future = self.periods.periods_after(user_id, period.ano, period.mes)
            orig_day = data.data.day
            for fp in future:
                ensure_period_mutable(self.db, user_id, fp.id)
                d = date_in_month(fp.ano, fp.mes, orig_day)
                clone = Income(
                    descricao=data.descricao,
                    valor=data.valor,
                    data=d,
                    recorrente=False,
                    period_id=fp.id,
                    categoria_id=data.categoria_id,
                    user_id=user_id,
                )
                self.incomes.create(clone)
                created.append(clone)
        return created

    def update(self, user_id: UUID, income_id: UUID, data: IncomeUpdate) -> Income:
        inc = self.incomes.get_by_id(income_id, user_id)
        if inc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Income not found")
        ensure_period_mutable(self.db, user_id, inc.period_id)
        if data.descricao is not None:
            inc.descricao = data.descricao
        if data.valor is not None:
            inc.valor = data.valor
        if data.data is not None:
            inc.data = data.data
        if data.period_id is not None:
            self._validate_refs(user_id, data.period_id, inc.categoria_id)
            inc.period_id = data.period_id
        if data.categoria_id is not None:
            self._validate_refs(user_id, inc.period_id, data.categoria_id)
            inc.categoria_id = data.categoria_id
        if data.recorrente is not None:
            inc.recorrente = data.recorrente
        return self.incomes.update(inc)

    def delete(self, user_id: UUID, income_id: UUID) -> None:
        inc = self.incomes.get_by_id(income_id, user_id)
        if inc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Income not found")
        ensure_period_mutable(self.db, user_id, inc.period_id)
        self.db.execute(
            update(GoalTransaction)
            .where(
                GoalTransaction.income_id == income_id,
                GoalTransaction.user_id == user_id,
            )
            .values(income_id=None)
        )
        self.incomes.delete(inc)

    def list_by_period(self, user_id: UUID, period_id: UUID) -> list[Income]:
        p = self.periods.get_by_id(period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        return self.incomes.list_by_period(user_id, period_id)

    def get(self, user_id: UUID, income_id: UUID) -> Income:
        inc = self.incomes.get_by_id(income_id, user_id)
        if inc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Income not found")
        return inc
