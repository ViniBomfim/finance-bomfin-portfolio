from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, category_id: UUID, user_id: UUID) -> Category | None:
        c = self.db.get(Category, category_id)
        if c is None or c.user_id != user_id:
            return None
        return c

    def list_by_user(self, user_id: UUID, tipo: str | None = None) -> list[Category]:
        stmt = select(Category).where(Category.user_id == user_id)
        if tipo is not None:
            stmt = stmt.where(Category.tipo == tipo)
        stmt = stmt.order_by(Category.nome)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, category: Category) -> Category:
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        return category

    def update(self, category: Category) -> Category:
        self.db.commit()
        self.db.refresh(category)
        return category

    def delete(self, category: Category) -> None:
        self.db.delete(category)
        self.db.commit()
