from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.schemas.category_schema import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryCreate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> CategoryResponse:
    c = CategoryService(db).create(user_id, data)
    return CategoryResponse.model_validate(c)


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    tipo: str | None = Query(None, pattern="^(income|expense)$"),
) -> list[CategoryResponse]:
    rows = CategoryService(db).list_all(user_id, tipo=tipo)
    return [CategoryResponse.model_validate(c) for c in rows]


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(category_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> CategoryResponse:
    c = CategoryService(db).get(user_id, category_id)
    return CategoryResponse.model_validate(c)


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> CategoryResponse:
    c = CategoryService(db).update(user_id, category_id, data)
    return CategoryResponse.model_validate(c)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> None:
    CategoryService(db).delete(user_id, category_id)
