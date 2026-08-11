from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.username import normalize_username
from app.models.user import AccountStatus, User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_username(self, username: str) -> User | None:
        normalized = normalize_username(username)
        stmt = select(User).where(User.username == normalized)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_active(self) -> list[User]:
        stmt = (
            select(User)
            .where(User.account_status == AccountStatus.ACTIVE.value)
            .order_by(User.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_pending(self) -> list[User]:
        stmt = (
            select(User)
            .where(User.account_status == AccountStatus.PENDING.value)
            .order_by(User.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_all(self) -> list[User]:
        stmt = select(User).order_by(User.created_at.asc())
        return list(self.db.execute(stmt).scalars().all())

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()
