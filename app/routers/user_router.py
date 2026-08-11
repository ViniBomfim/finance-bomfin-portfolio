from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentAdminUser, CurrentUser
from app.core.security import get_password_hash
from app.database.connection import get_db
from app.repositories.user_repository import UserRepository
from app.repositories.spender_repository import SpenderRepository
from app.schemas.auth_schema import RegisterRequest
from app.schemas.user_schema import (
    AccessRequestResponse,
    UserAdminCreateRequest,
    UserAdminResetPasswordRequest,
    UserAdminUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["users"])

_ALLOWED_AVATAR_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
_MAX_AVATAR_BYTES = 2 * 1024 * 1024


def _sniff_image_content_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
def update_me(
    data: UserUpdateRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> UserResponse:
    payload = data.model_dump(exclude_unset=True)
    if "name" in payload and payload["name"] is not None:
        user.name = payload["name"]
    if "me_spender_id" in payload:
        mid: UUID | None = payload["me_spender_id"]
        if mid is None:
            user.me_spender_id = None
        else:
            sp = SpenderRepository(db).get_by_id(mid, user.id)
            if sp is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Pessoa não encontrada ou não pertence a este usuário",
                )
            user.me_spender_id = sp.id
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/me/avatar", response_model=UserResponse)
async def upload_my_avatar(
    user: CurrentUser,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
) -> UserResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo vazio")
    if len(content) > _MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Imagem muito grande. Máximo: 2 MB.",
        )
    sniffed = _sniff_image_content_type(content)
    declared = (file.content_type or "").split(";")[0].strip().lower()
    content_type = sniffed or (declared if declared in _ALLOWED_AVATAR_TYPES else None)
    if content_type not in _ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato inválido. Use JPEG, PNG ou WebP.",
        )
    user.avatar_bytes = content
    user.avatar_content_type = content_type
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/me/avatar")
def get_my_avatar(user: CurrentUser) -> Response:
    if not user.avatar_bytes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sem foto de perfil")
    return Response(
        content=user.avatar_bytes,
        media_type=user.avatar_content_type or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.delete("/me/avatar", response_model=UserResponse)
def delete_my_avatar(
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> UserResponse:
    user.avatar_bytes = None
    user.avatar_content_type = None
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/access-requests", response_model=list[AccessRequestResponse])
def list_access_requests(
    _admin: CurrentAdminUser,
    db: Session = Depends(get_db),
) -> list[AccessRequestResponse]:
    pending = UserRepository(db).list_pending()
    return [AccessRequestResponse.model_validate(item) for item in pending]


@router.post("/{user_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
def approve_access_request(
    user_id: UUID,
    _admin: CurrentAdminUser,
    db: Session = Depends(get_db),
) -> None:
    AuthService(db).approve_pending_user(user_id)


@router.post("/{user_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_access_request(
    user_id: UUID,
    _admin: CurrentAdminUser,
    db: Session = Depends(get_db),
) -> None:
    AuthService(db).reject_pending_user(user_id)


@router.get("", response_model=list[UserResponse])
def list_users(
    _admin: CurrentAdminUser,
    db: Session = Depends(get_db),
) -> list[UserResponse]:
    users = UserRepository(db).list_active()
    return [UserResponse.model_validate(item) for item in users]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_as_admin(
    data: UserAdminCreateRequest,
    _admin: CurrentAdminUser,
    db: Session = Depends(get_db),
) -> UserResponse:
    try:
        user = AuthService(db).register_as_admin(
            RegisterRequest(
                username=data.username,
                name=data.name,
                email=data.email,
                password=data.password,
            )
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_400_BAD_REQUEST and exc.detail == "Email already registered":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="E-mail já cadastrado.",
            ) from exc
        if exc.status_code == status.HTTP_400_BAD_REQUEST and exc.detail == "Username already registered":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Usuário de login já cadastrado.",
            ) from exc
        raise
    user.is_admin = data.is_admin
    user.must_change_password = data.must_change_password
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user_as_admin(
    user_id: UUID,
    data: UserAdminUpdateRequest,
    admin: CurrentAdminUser,
    db: Session = Depends(get_db),
) -> UserResponse:
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    payload = data.model_dump(exclude_unset=True)
    if "username" in payload and payload["username"] is not None:
        new_username = payload["username"]
        if new_username != user.username:
            existing = repo.get_by_username(new_username)
            if existing is not None and existing.id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Usuário de login já cadastrado.",
                )
            user.username = new_username
    if "name" in payload and payload["name"] is not None:
        user.name = payload["name"]
    if "email" in payload and payload["email"] is not None:
        new_email = str(payload["email"])
        if new_email != user.email:
            existing = repo.get_by_email(new_email)
            if existing is not None and existing.id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="E-mail já cadastrado.",
                )
            user.email = new_email
    if "is_admin" in payload and payload["is_admin"] is not None:
        if admin.id == user.id and payload["is_admin"] is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Você não pode remover seu próprio acesso de admin",
            )
        user.is_admin = payload["is_admin"]

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não foi possível atualizar o usuário (login ou e-mail já existente).",
        ) from exc
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_as_admin(
    user_id: UUID,
    admin: CurrentAdminUser,
    db: Session = Depends(get_db),
) -> None:
    if admin.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Você não pode excluir o próprio usuário admin em uso.",
        )
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    repo.delete(user)


@router.patch("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password_as_admin(
    user_id: UUID,
    data: UserAdminResetPasswordRequest,
    _admin: CurrentAdminUser,
    db: Session = Depends(get_db),
) -> None:
    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    user.password_hash = get_password_hash(data.password)
    user.must_change_password = False
    db.commit()
