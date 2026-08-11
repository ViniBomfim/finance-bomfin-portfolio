from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.schemas.goal_schema import (
    GoalCreate,
    GoalPoolSummaryResponse,
    GoalProgressResponse,
    GoalResponse,
    GoalTransactionCreate,
    GoalTransactionResponse,
    GoalUpdate,
)
from app.services.goal_service import GoalService

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(data: GoalCreate, user_id: CurrentUserId, db: Session = Depends(get_db)) -> GoalResponse:
    g = GoalService(db).create(user_id, data)
    return GoalResponse.model_validate(g)


@router.get("", response_model=list[GoalResponse])
def list_goals(user_id: CurrentUserId, db: Session = Depends(get_db)) -> list[GoalResponse]:
    rows = GoalService(db).list_goals(user_id)
    return [GoalResponse.model_validate(x) for x in rows]


@router.get("/pool-summary", response_model=GoalPoolSummaryResponse)
def goal_pool_summary(
    user_id: CurrentUserId,
    period_id: UUID = Query(...),
    db: Session = Depends(get_db),
) -> GoalPoolSummaryResponse:
    return GoalService(db).pool_summary(user_id, period_id)


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(goal_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> GoalResponse:
    g = GoalService(db).get(user_id, goal_id)
    return GoalResponse.model_validate(g)


@router.get("/{goal_id}/progress", response_model=GoalProgressResponse)
def goal_progress(goal_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> GoalProgressResponse:
    return GoalService(db).progress(user_id, goal_id)


@router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: UUID,
    data: GoalUpdate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> GoalResponse:
    g = GoalService(db).update(user_id, goal_id, data)
    return GoalResponse.model_validate(g)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> None:
    GoalService(db).delete(user_id, goal_id)


@router.post("/{goal_id}/transactions", response_model=GoalTransactionResponse, status_code=status.HTTP_201_CREATED)
def add_goal_transaction(
    goal_id: UUID,
    data: GoalTransactionCreate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> GoalTransactionResponse:
    tx = GoalService(db).add_transaction(user_id, goal_id, data)
    return GoalTransactionResponse.model_validate(tx)


@router.get("/{goal_id}/transactions", response_model=list[GoalTransactionResponse])
def list_goal_transactions(
    goal_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> list[GoalTransactionResponse]:
    rows = GoalService(db).list_transactions(user_id, goal_id)
    return [GoalTransactionResponse.model_validate(x) for x in rows]


@router.delete("/{goal_id}/transactions/{tx_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal_transaction(
    goal_id: UUID,
    tx_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> None:
    GoalService(db).delete_transaction(user_id, goal_id, tx_id)
