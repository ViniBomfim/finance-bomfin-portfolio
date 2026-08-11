from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.installment import Installment
from app.repositories.installment_repository import InstallmentRepository
from app.services.period_mutability import ensure_period_mutable


class InstallmentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.installments = InstallmentRepository(db)

    def list_by_expense(self, user_id: UUID, expense_id: UUID) -> list[Installment]:
        return self.installments.list_by_expense(user_id, expense_id)

    def mark_paid(self, user_id: UUID, installment_id: UUID, pago: bool = True) -> Installment:
        inst = self.installments.get_by_id(installment_id, user_id)
        if inst is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Installment not found")
        ensure_period_mutable(self.db, user_id, inst.period_id)
        inst.pago = pago
        return self.installments.update(inst)
