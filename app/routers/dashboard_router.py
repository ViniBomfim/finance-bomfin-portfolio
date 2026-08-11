from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.schemas.dashboard_schema import DashboardSummary
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Dashboard do período",
    description=(
        "Saldo mensal (receitas − despesas), despesas por categoria, progresso das metas, "
        "totais por cartão e patrimônio simplificado."
    ),
)
def dashboard_summary(
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    period_id: UUID = Query(..., description="Período (mês) de referência"),
) -> DashboardSummary:
    return DashboardService(db).summary_cached(user_id, period_id)
