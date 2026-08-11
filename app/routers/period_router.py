from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.schemas.period_schema import CreateYearRequest, PeriodResponse
from app.services.period_service import PeriodService

router = APIRouter(prefix="/periods", tags=["periods"])


@router.get("", response_model=list[PeriodResponse])
def list_periods(user_id: CurrentUserId, db: Session = Depends(get_db)) -> list[PeriodResponse]:
    rows = PeriodService(db).list_periods(user_id)
    return [PeriodResponse.model_validate(p) for p in rows]


@router.get("/{period_id}", response_model=PeriodResponse)
def get_period(period_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> PeriodResponse:
    p = PeriodService(db).get(user_id, period_id)
    return PeriodResponse.model_validate(p)


@router.post("/year", response_model=list[PeriodResponse])
def create_year(
    body: CreateYearRequest,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> list[PeriodResponse]:
    rows = PeriodService(db).create_year(user_id, body.ano)
    return [PeriodResponse.model_validate(p) for p in rows]


@router.post("/{period_id}/close", response_model=PeriodResponse)
def close_period(period_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> PeriodResponse:
    p = PeriodService(db).close_period(user_id, period_id)
    return PeriodResponse.model_validate(p)


@router.post("/{period_id}/open", response_model=PeriodResponse)
def reopen_period(period_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> PeriodResponse:
    p = PeriodService(db).reopen_period(user_id, period_id)
    return PeriodResponse.model_validate(p)
