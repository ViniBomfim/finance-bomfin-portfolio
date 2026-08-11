from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.schemas.budget_schema import (
    BudgetCompareRow,
    BudgetCreate,
    BudgetResponse,
    BudgetUpdate,
    ReplicateYearBudgetsRequest,
)
from app.services.budget_service import BudgetService
from app.services.period_service import PeriodService

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(
    data: BudgetCreate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> BudgetResponse:
    b = BudgetService(db).create(user_id, data)
    return BudgetResponse.model_validate(b)


@router.get("/compare", response_model=list[BudgetCompareRow])
def compare_budgets(
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    period_id: UUID = Query(...),
) -> list[BudgetCompareRow]:
    return BudgetService(db).compare(user_id, period_id)


@router.post("/replicate-year", response_model=list[BudgetResponse])
def replicate_year_budgets(
    body: ReplicateYearBudgetsRequest,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> list[BudgetResponse]:
    PeriodService(db).create_year(user_id, body.to_ano)
    rows = BudgetService(db).replicate_budgets_between_years(user_id, body.from_ano, body.to_ano)
    return [BudgetResponse.model_validate(x) for x in rows]


@router.post("/copy-from-previous", response_model=list[BudgetResponse])
def copy_budgets_from_previous_month(
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    period_id: UUID = Query(..., description="Período destino (recebe cópia do mês civil anterior)"),
) -> list[BudgetResponse]:
    rows = BudgetService(db).copy_from_previous_month(user_id, period_id)
    return [BudgetResponse.model_validate(x) for x in rows]


@router.get("", response_model=list[BudgetResponse])
def list_budgets(
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    period_id: UUID = Query(...),
) -> list[BudgetResponse]:
    rows = BudgetService(db).list_by_period(user_id, period_id)
    return [BudgetResponse.model_validate(x) for x in rows]


@router.get("/{budget_id}", response_model=BudgetResponse)
def get_budget(budget_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> BudgetResponse:
    b = BudgetService(db).get(user_id, budget_id)
    return BudgetResponse.model_validate(b)


@router.patch("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: UUID,
    data: BudgetUpdate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> BudgetResponse:
    b = BudgetService(db).update(user_id, budget_id, data)
    return BudgetResponse.model_validate(b)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(budget_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> None:
    BudgetService(db).delete(user_id, budget_id)
