from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.expenses.schemas import ExpenseListFilter
from app.expenses.service import ExpenseService


def get_expense_service(db: Session = Depends(get_db)) -> ExpenseService:
    return ExpenseService(db)


def get_expense_list_filter(
    period_id: UUID | None = Query(
        default=None,
        description="Filtrar despesas pelo período",
    ),
    categoria_id: UUID | None = Query(
        default=None,
        description="Filtrar despesas pela categoria",
    ),
) -> ExpenseListFilter:
    if period_id is None and categoria_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe period_id ou categoria_id",
        )
    return ExpenseListFilter(period_id=period_id, categoria_id=categoria_id)


ExpenseServiceDep = Annotated[ExpenseService, Depends(get_expense_service)]
ExpenseListFilterDep = Annotated[ExpenseListFilter, Depends(get_expense_list_filter)]
