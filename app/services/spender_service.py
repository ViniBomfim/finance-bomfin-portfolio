from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.spender import Spender
from app.models.user import User
from app.repositories.spender_repository import SpenderRepository
from app.schemas.spender_schema import SpenderCreate, SpenderUpdate


class SpenderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SpenderRepository(db)

    def list(self, user_id: UUID) -> list[Spender]:
        return self.repo.list_by_user(user_id, only_global=True)

    def create(self, user_id: UUID, data: SpenderCreate) -> Spender:
        s = Spender(nome=data.nome.strip(), user_id=user_id)
        return self.repo.create(s)

    def update(self, user_id: UUID, spender_id: UUID, data: SpenderUpdate) -> Spender:
        s = self.repo.get_by_id(spender_id, user_id)
        if s is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spender not found")
        if data.nome is not None:
            s.nome = data.nome.strip()
        return self.repo.update(s)

    def delete(self, user_id: UUID, spender_id: UUID) -> None:
        s = self.repo.get_by_id(spender_id, user_id)
        if s is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spender not found")
        if self.repo.count_share_rows(spender_id) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não é possível excluir: há lançamentos de cartão vinculados a esta pessoa.",
            )
        self.db.execute(update(User).where(User.me_spender_id == spender_id).values(me_spender_id=None))
        self.db.delete(s)
        self.db.commit()
