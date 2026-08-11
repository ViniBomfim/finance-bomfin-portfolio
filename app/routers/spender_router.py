from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.schemas.spender_schema import SpenderCreate, SpenderResponse, SpenderUpdate
from app.services.spender_service import SpenderService

router = APIRouter(prefix="/spenders", tags=["spenders"])


@router.get("", response_model=list[SpenderResponse])
def list_spenders(user_id: CurrentUserId, db: Session = Depends(get_db)) -> list[SpenderResponse]:
    rows = SpenderService(db).list(user_id)
    return [SpenderResponse.model_validate(x) for x in rows]


@router.post("", response_model=SpenderResponse, status_code=status.HTTP_201_CREATED)
def create_spender(
    data: SpenderCreate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> SpenderResponse:
    s = SpenderService(db).create(user_id, data)
    return SpenderResponse.model_validate(s)


@router.patch("/{spender_id}", response_model=SpenderResponse)
def update_spender(
    spender_id: UUID,
    data: SpenderUpdate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> SpenderResponse:
    s = SpenderService(db).update(user_id, spender_id, data)
    return SpenderResponse.model_validate(s)


@router.delete("/{spender_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_spender(spender_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> None:
    SpenderService(db).delete(user_id, spender_id)
