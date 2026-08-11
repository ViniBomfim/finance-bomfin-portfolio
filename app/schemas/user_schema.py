from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.username import is_valid_username, normalize_username


class UserResponse(BaseModel):
    id: UUID
    username: str
    name: str
    email: EmailStr
    is_admin: bool = False
    me_spender_id: UUID | None = None
    has_avatar: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    me_spender_id: UUID | None = Field(None, description="Pessoa cadastrada que representa você; null para limpar")


class UserAdminUpdateRequest(BaseModel):
    username: str | None = Field(None, min_length=1, max_length=64)
    name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    is_admin: bool | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = normalize_username(value)
        if not is_valid_username(normalized):
            raise ValueError("Usuário inválido. Informe de 1 a 64 caracteres.")
        return normalized


class UserAdminResetPasswordRequest(BaseModel):
    password: str = Field(..., min_length=6, max_length=128)


class AccessRequestResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    created_at: datetime

    model_config = {"from_attributes": True}


class UserAdminCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    is_admin: bool = False
    must_change_password: bool = True

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        normalized = normalize_username(value)
        if not is_valid_username(normalized):
            raise ValueError("Usuário inválido. Informe de 1 a 64 caracteres.")
        return normalized
