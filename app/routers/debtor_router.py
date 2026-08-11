from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.schemas.debtor_schema import (
    DebtorLoanCreate,
    DebtorLoanResponse,
    DebtorLoanUpdate,
    DebtorPaymentCreate,
)
from app.services.debtor_service import DebtorService

router = APIRouter(prefix="/debtors", tags=["debtors"])


@router.get("", response_model=list[DebtorLoanResponse])
def list_debtors(user_id: CurrentUserId, db: Session = Depends(get_db)) -> list[DebtorLoanResponse]:
    rows = DebtorService(db).list_loans(user_id)
    return [DebtorLoanResponse.model_validate(x) for x in rows]


@router.post("", response_model=DebtorLoanResponse, status_code=status.HTTP_201_CREATED)
def create_debtor(
    data: DebtorLoanCreate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> DebtorLoanResponse:
    row = DebtorService(db).create_loan(user_id, data)
    return DebtorLoanResponse.model_validate(row)


@router.patch("/{loan_id}", response_model=DebtorLoanResponse)
def update_debtor(
    loan_id: UUID,
    data: DebtorLoanUpdate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> DebtorLoanResponse:
    row = DebtorService(db).update_loan(user_id, loan_id, data)
    return DebtorLoanResponse.model_validate(row)


@router.delete("/{loan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_debtor(loan_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> None:
    DebtorService(db).delete_loan(user_id, loan_id)


@router.post("/{loan_id}/payments", response_model=DebtorLoanResponse)
def add_debtor_payment(
    loan_id: UUID,
    data: DebtorPaymentCreate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> DebtorLoanResponse:
    row = DebtorService(db).add_payment(user_id, loan_id, data)
    return DebtorLoanResponse.model_validate(row)


@router.delete("/payments/{payment_id}", response_model=DebtorLoanResponse)
def delete_debtor_payment(payment_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> DebtorLoanResponse:
    row = DebtorService(db).delete_payment(user_id, payment_id)
    return DebtorLoanResponse.model_validate(row)
