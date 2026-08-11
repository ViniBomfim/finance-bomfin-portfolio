from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.schemas.income_schema import IncomeCreate, IncomeResponse, IncomeUpdate
from app.services.income_service import IncomeService

router = APIRouter(prefix="/incomes", tags=["incomes"])


@router.post("", response_model=list[IncomeResponse], status_code=status.HTTP_201_CREATED)
def create_income(
    data: IncomeCreate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> list[IncomeResponse]:
    rows = IncomeService(db).create(user_id, data)
    return [IncomeResponse.model_validate(x) for x in rows]


@router.get("", response_model=list[IncomeResponse])
def list_incomes(
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    period_id: UUID = Query(...),
) -> list[IncomeResponse]:
    rows = IncomeService(db).list_by_period(user_id, period_id)
    return [IncomeResponse.model_validate(x) for x in rows]


@router.get("/{income_id}", response_model=IncomeResponse)
def get_income(income_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> IncomeResponse:
    inc = IncomeService(db).get(user_id, income_id)
    return IncomeResponse.model_validate(inc)


@router.patch("/{income_id}", response_model=IncomeResponse)
def update_income(
    income_id: UUID,
    data: IncomeUpdate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> IncomeResponse:
    inc = IncomeService(db).update(user_id, income_id, data)
    return IncomeResponse.model_validate(inc)


@router.delete("/{income_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_income(income_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> None:
    IncomeService(db).delete(user_id, income_id)
