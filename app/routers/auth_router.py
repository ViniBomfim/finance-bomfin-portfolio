from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.schemas.auth_schema import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user_schema import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)) -> UserResponse:
    try:
        user = AuthService(db).register(data)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_400_BAD_REQUEST and exc.detail == "Email already registered":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="E-mail já cadastrado.",
            ) from exc
        if exc.status_code == status.HTTP_400_BAD_REQUEST and exc.detail == "Username already registered":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuário de login já cadastrado.",
            ) from exc
        raise
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    token = AuthService(db).login(data)
    return TokenResponse(access_token=token)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(user_id: CurrentUserId, db: Session = Depends(get_db)) -> TokenResponse:
    token = AuthService.issue_token_for_user(user_id)
    return TokenResponse(access_token=token)
