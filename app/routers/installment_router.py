from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.schemas.installment_schema import InstallmentResponse
from app.services.installment_service import InstallmentService

router = APIRouter(prefix="/installments", tags=["installments"])


@router.get("", response_model=list[InstallmentResponse])
def list_installments(
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    expense_id: UUID = Query(...),
) -> list[InstallmentResponse]:
    rows = InstallmentService(db).list_by_expense(user_id, expense_id)
    return [InstallmentResponse.model_validate(x) for x in rows]


@router.post("/{installment_id}/paid", response_model=InstallmentResponse)
def mark_installment_paid(
    installment_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    pago: bool = Query(True),
) -> InstallmentResponse:
    inst = InstallmentService(db).mark_paid(user_id, installment_id, pago=pago)
    return InstallmentResponse.model_validate(inst)
