from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import AccountStatus, User
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import LoginRequest, RegisterRequest
from app.services.admin_management_service import AdminManagementService


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def register(
        self,
        data: RegisterRequest,
        *,
        account_status: AccountStatus = AccountStatus.PENDING,
    ) -> User:
        if self.users.get_by_email(str(data.email)) is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
        if self.users.get_by_username(data.username) is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")

        display_name = (data.name or data.username).strip()
        user = User(
            username=data.username,
            name=display_name,
            email=str(data.email),
            password_hash=get_password_hash(data.password),
            account_status=account_status.value,
        )
        return self.users.create(user)

    def register_as_admin(self, data: RegisterRequest) -> User:
        return self.register(data, account_status=AccountStatus.ACTIVE)

    def login(self, data: LoginRequest) -> str:
        user = self.users.get_by_username(data.username)
        if user is None and "@" in data.username:
            user = self.users.get_by_email(data.username)
        if user is None or not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        if user.account_status == AccountStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Conta aguardando aprovação do administrador.",
            )
        token = create_access_token(subject=user.id)
        try:
            AdminManagementService(self.db).record_login(user)
        except Exception:
            self.db.rollback()
        return token

    def approve_pending_user(self, user_id: UUID) -> User:
        user = self.users.get_by_id(user_id)
        if user is None or user.account_status != AccountStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitação não encontrada.",
            )
        user.account_status = AccountStatus.ACTIVE.value
        self.db.commit()
        self.db.refresh(user)
        return user

    def reject_pending_user(self, user_id: UUID) -> None:
        user = self.users.get_by_id(user_id)
        if user is None or user.account_status != AccountStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solicitação não encontrada.",
            )
        self.users.delete(user)

    @staticmethod
    def issue_token_for_user(user_id: UUID) -> str:
        return create_access_token(subject=user_id)
