from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.schemas.budget_schema import BudgetCompareRow
from app.schemas.reports_schema import CategoryExpenseReportRow, MonthlyFlowRow
from app.services.reports_service import ReportsService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/monthly-flow", response_model=list[MonthlyFlowRow])
def report_monthly_flow(
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    ano: int = Query(..., ge=2000, le=2100),
) -> list[MonthlyFlowRow]:
    return ReportsService(db).monthly_flow(user_id, ano)


@router.get("/expenses-by-category", response_model=list[CategoryExpenseReportRow])
def report_expenses_by_category(
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    period_id: UUID = Query(...),
) -> list[CategoryExpenseReportRow]:
    return ReportsService(db).expenses_by_category(user_id, period_id)


@router.get("/budget-vs-actual", response_model=list[BudgetCompareRow])
def report_budget_vs_actual(
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    period_id: UUID = Query(...),
) -> list[BudgetCompareRow]:
    return ReportsService(db).budget_vs_actual(user_id, period_id)
