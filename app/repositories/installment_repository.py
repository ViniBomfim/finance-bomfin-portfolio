from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.expenses.model import Expense
from app.models.installment import Installment


class InstallmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, installment_id: UUID, user_id: UUID) -> Installment | None:
        inst = self.db.get(Installment, installment_id)
        if inst is None:
            return None
        exp = self.db.get(Expense, inst.expense_id)
        if exp is None or exp.user_id != user_id:
            return None
        return inst

    def list_by_expense(self, user_id: UUID, expense_id: UUID) -> list[Installment]:
        stmt = (
            select(Installment)
            .join(Expense, Installment.expense_id == Expense.id)
            .where(Installment.expense_id == expense_id, Expense.user_id == user_id)
            .order_by(Installment.numero)
        )
        return list(self.db.execute(stmt).scalars().all())

    def create_many(self, items: list[Installment]) -> list[Installment]:
        for x in items:
            self.db.add(x)
        self.db.commit()
        for x in items:
            self.db.refresh(x)
        return items

    def update(self, inst: Installment) -> Installment:
        self.db.commit()
        self.db.refresh(inst)
        return inst
