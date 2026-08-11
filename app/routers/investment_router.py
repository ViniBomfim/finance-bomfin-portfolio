from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.repositories.listed_asset_repository import ListedAssetRepository
from app.schemas.investment_schema import InvestmentCreate, InvestmentResponse, InvestmentUpdate
from app.schemas.listed_asset_schema import ListedAssetResponse
from app.services.investment_service import InvestmentService

router = APIRouter(prefix="/investments", tags=["investments"])


@router.get("/catalog", response_model=list[ListedAssetResponse])
def list_listed_assets(user_id: CurrentUserId, db: Session = Depends(get_db)) -> list[ListedAssetResponse]:
    rows = ListedAssetRepository(db).list_all_ordered()
    return [ListedAssetResponse.model_validate(x) for x in rows]


@router.get("", response_model=list[InvestmentResponse])
def list_investments(user_id: CurrentUserId, db: Session = Depends(get_db)) -> list[InvestmentResponse]:
    rows = InvestmentService(db).list(user_id)
    return [InvestmentResponse.model_validate(x) for x in rows]


@router.get("/total", response_model=dict)
def total_patrimonio(user_id: CurrentUserId, db: Session = Depends(get_db)) -> dict[str, float]:
    total = InvestmentService(db).total_patrimonio(user_id)
    return {"total_valor_atual": total}


@router.post("", response_model=InvestmentResponse, status_code=status.HTTP_201_CREATED)
def create_investment(
    data: InvestmentCreate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> InvestmentResponse:
    row = InvestmentService(db).create(user_id, data)
    return InvestmentResponse.model_validate(row)


@router.patch("/{investment_id}", response_model=InvestmentResponse)
def update_investment(
    investment_id: UUID,
    data: InvestmentUpdate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> InvestmentResponse:
    row = InvestmentService(db).update(user_id, investment_id, data)
    return InvestmentResponse.model_validate(row)


@router.delete("/{investment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investment(investment_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> None:
    InvestmentService(db).delete(user_id, investment_id)
