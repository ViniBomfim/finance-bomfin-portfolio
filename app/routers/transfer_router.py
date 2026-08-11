from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.schemas.transfer_schema import TransferCreate, TransferResponse
from app.services.transfer_service import TransferService

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.post("", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
def create_transfer(
    data: TransferCreate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> TransferResponse:
    t = TransferService(db).create(user_id, data)
    return TransferResponse.model_validate(t)


@router.get("", response_model=list[TransferResponse])
def list_transfers(user_id: CurrentUserId, db: Session = Depends(get_db)) -> list[TransferResponse]:
    rows = TransferService(db).list_transfers(user_id)
    return [TransferResponse.model_validate(x) for x in rows]
