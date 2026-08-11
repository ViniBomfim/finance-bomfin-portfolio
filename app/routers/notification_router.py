from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.schemas.notification_schema import (
    NotificationGenerateResponse,
    NotificationListResponse,
    NotificationMarkAllResponse,
    NotificationResponse,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(user_id: CurrentUserId, db: Session = Depends(get_db)) -> NotificationListResponse:
    return NotificationService(db).list_unread(user_id)


@router.get("/historico", response_model=NotificationListResponse)
def list_notification_history(
    user_id: CurrentUserId, db: Session = Depends(get_db)
) -> NotificationListResponse:
    return NotificationService(db).list_historico(user_id)


@router.post("/gerar", response_model=NotificationGenerateResponse)
def generate_notifications(
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    force: bool = Query(False, description="Ignora o limite de uma geração por dia"),
) -> NotificationGenerateResponse:
    return NotificationService(db).gerar_notificacoes(user_id, force=force)


@router.patch("/todas-lidas", response_model=NotificationMarkAllResponse)
def mark_all_notifications_read(
    user_id: CurrentUserId, db: Session = Depends(get_db)
) -> NotificationMarkAllResponse:
    count = NotificationService(db).mark_all_read(user_id)
    return NotificationMarkAllResponse(count=count)


@router.patch("/{notification_id}/lida", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> NotificationResponse:
    return NotificationService(db).mark_read(user_id, notification_id)


@router.delete("/historico", response_model=NotificationMarkAllResponse)
def clear_notification_history(
    user_id: CurrentUserId, db: Session = Depends(get_db)
) -> NotificationMarkAllResponse:
    count = NotificationService(db).limpar_historico_antigo(user_id)
    return NotificationMarkAllResponse(count=count)
