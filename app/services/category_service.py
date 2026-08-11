from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.category import Category
from app.repositories.category_repository import CategoryRepository
from app.schemas.category_schema import CategoryCreate, CategoryUpdate

# Cores distintas para gráficos e listas; escolhida automaticamente na criação quando `cor` não é enviada.
_CATEGORY_PALETTE: tuple[str, ...] = (
    "#3d8bfd",
    "#34c759",
    "#f5a623",
    "#bd10e0",
    "#d0021b",
    "#7b68ee",
    "#50c878",
    "#8b572a",
    "#14b8a6",
    "#ec4899",
    "#2563eb",
    "#f97316",
)


class CategoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.categories = CategoryRepository(db)

    def _next_auto_color(self, user_id: UUID, tipo: str) -> str:
        existing = self.categories.list_by_user(user_id, tipo=tipo)
        idx = len(existing) % len(_CATEGORY_PALETTE)
        return _CATEGORY_PALETTE[idx]

    def create(self, user_id: UUID, data: CategoryCreate) -> Category:
        cor_in = (data.cor or "").strip()
        cor = cor_in if cor_in else self._next_auto_color(user_id, data.tipo)
        c = Category(nome=data.nome, cor=cor, tipo=data.tipo, user_id=user_id)
        return self.categories.create(c)

    def update(self, user_id: UUID, category_id: UUID, data: CategoryUpdate) -> Category:
        c = self.categories.get_by_id(category_id, user_id)
        if c is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        if data.nome is not None:
            c.nome = data.nome
        if data.cor is not None:
            c.cor = data.cor
        if data.tipo is not None:
            c.tipo = data.tipo
        return self.categories.update(c)

    def delete(self, user_id: UUID, category_id: UUID) -> None:
        c = self.categories.get_by_id(category_id, user_id)
        if c is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        self.categories.delete(c)

    def list_all(self, user_id: UUID, tipo: str | None = None) -> list[Category]:
        return self.categories.list_by_user(user_id, tipo=tipo)

    def get(self, user_id: UUID, category_id: UUID) -> Category:
        c = self.categories.get_by_id(category_id, user_id)
        if c is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        return c
