from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.debtor_loan import DebtorLoan
from app.models.debtor_payment import DebtorPayment
from app.services.dashboard_cache import DashboardCache


class DebtorRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_loans_by_user(self, user_id: UUID) -> list[DebtorLoan]:
        stmt = (
            select(DebtorLoan)
            .options(selectinload(DebtorLoan.pagamentos), selectinload(DebtorLoan.spender))
            .where(DebtorLoan.user_id == user_id)
            .order_by(DebtorLoan.data_emprestimo.desc(), DebtorLoan.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_loan_by_id(self, loan_id: UUID, user_id: UUID) -> DebtorLoan | None:
        stmt = (
            select(DebtorLoan)
            .options(selectinload(DebtorLoan.pagamentos), selectinload(DebtorLoan.spender))
            .where(DebtorLoan.id == loan_id, DebtorLoan.user_id == user_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create_loan(self, loan: DebtorLoan) -> DebtorLoan:
        self.db.add(loan)
        self.db.commit()
        self.db.refresh(loan)
        DashboardCache.invalidate_user(loan.user_id)
        return loan

    def update_loan(self, loan: DebtorLoan) -> DebtorLoan:
        self.db.commit()
        self.db.refresh(loan)
        DashboardCache.invalidate_user(loan.user_id)
        return loan

    def delete_loan(self, loan: DebtorLoan) -> None:
        user_id = loan.user_id
        self.db.delete(loan)
        self.db.commit()
        DashboardCache.invalidate_user(user_id)

    def create_payment(self, payment: DebtorPayment) -> DebtorPayment:
        loan = self.db.get(DebtorLoan, payment.emprestimo_id)
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        if loan is not None:
            DashboardCache.invalidate_user(loan.user_id)
        return payment

    def get_payment_by_id(self, payment_id: UUID, user_id: UUID) -> DebtorPayment | None:
        stmt = (
            select(DebtorPayment)
            .join(DebtorLoan, DebtorPayment.emprestimo_id == DebtorLoan.id)
            .where(DebtorPayment.id == payment_id, DebtorLoan.user_id == user_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def delete_payment(self, payment: DebtorPayment) -> None:
        loan = self.db.get(DebtorLoan, payment.emprestimo_id)
        self.db.delete(payment)
        self.db.commit()
        if loan is not None:
            DashboardCache.invalidate_user(loan.user_id)
