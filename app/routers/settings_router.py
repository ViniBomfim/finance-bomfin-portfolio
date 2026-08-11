from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.database.connection import get_db
from app.schemas.session_settings_schema import SessionSettingsResponse
from app.services.session_settings_service import SessionSettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/session", response_model=SessionSettingsResponse)
def get_session_settings(
    _user: CurrentUser,
    db: Session = Depends(get_db),
) -> SessionSettingsResponse:
    data = SessionSettingsService(db).get_session_settings()
    return SessionSettingsResponse.model_validate(data)
