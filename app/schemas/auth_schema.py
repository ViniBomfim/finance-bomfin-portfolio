from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.username import is_valid_username, normalize_username


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        normalized = normalize_username(value)
        if not is_valid_username(normalized):
            raise ValueError("Usuário inválido. Informe de 1 a 64 caracteres.")
        return normalized


class LoginRequest(BaseModel):
    # Aceita username ou e-mail (e-mails podem passar de 64 caracteres).
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)

    @field_validator("username")
    @classmethod
    def normalize_login_username(cls, value: str) -> str:
        return normalize_username(value)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
