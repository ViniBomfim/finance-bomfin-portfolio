from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentAdminUser
from app.database.connection import get_db
from app.schemas.admin_management_schema import AdminManagementStats, SystemErrorLogRow
from app.schemas.session_settings_schema import (
    SessionSettingsDefaults,
    SessionSettingsResponse,
    SessionSettingsUpdateRequest,
)
from app.services.admin_management_service import AdminManagementService
from app.services.session_settings_service import SessionSettingsService

router = APIRouter(prefix="/admin/management", tags=["admin-management"])


@router.get("/stats", response_model=AdminManagementStats)
def management_stats(
    _admin: CurrentAdminUser,
    db: Session = Depends(get_db),
) -> AdminManagementStats:
    data = AdminManagementService(db).get_stats()
    return AdminManagementStats.model_validate(data)


@router.get("/error-logs", response_model=list[SystemErrorLogRow])
def management_error_logs(
    _admin: CurrentAdminUser,
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=500),
) -> list[SystemErrorLogRow]:
    rows = AdminManagementService(db).list_error_logs(limit=limit)
    return [SystemErrorLogRow.model_validate(r) for r in rows]


@router.get("/session-settings", response_model=SessionSettingsResponse)
def get_session_settings_admin(
    _admin: CurrentAdminUser,
    db: Session = Depends(get_db),
) -> SessionSettingsResponse:
    data = SessionSettingsService(db).get_session_settings()
    return SessionSettingsResponse.model_validate(data)


@router.get("/session-settings/limits", response_model=SessionSettingsDefaults)
def get_session_settings_limits(_admin: CurrentAdminUser) -> SessionSettingsDefaults:
    return SessionSettingsDefaults()


@router.patch("/session-settings", response_model=SessionSettingsResponse)
def patch_session_settings(
    body: SessionSettingsUpdateRequest,
    _admin: CurrentAdminUser,
    db: Session = Depends(get_db),
) -> SessionSettingsResponse:
    data = SessionSettingsService(db).update_session_settings(
        minutes=body.inactivity_logout_minutes,
        enabled=body.inactivity_logout_enabled,
    )
    return SessionSettingsResponse.model_validate(data)
