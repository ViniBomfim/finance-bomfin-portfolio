from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.database.url import DEFAULT_SQLITE_URL, normalize_database_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str | None = None
    # Alias comum no painel do Supabase / Render (connection string URI).
    SUPABASE_DB_URL: str | None = None
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    # Roda `alembic upgrade head` na subida quando o banco é PostgreSQL (ex.: Supabase).
    # No Render/Docker use false — migrações rodam em scripts/render-start.sh.
    RUN_MIGRATIONS_ON_STARTUP: bool = True
    # Origens CORS separadas por vírgula (ex.: https://your-frontend.example.com). Vazio = *.
    CORS_ORIGINS: str = ""

    @model_validator(mode="after")
    def resolve_database_url(self) -> Self:
        raw = (self.DATABASE_URL or self.SUPABASE_DB_URL or DEFAULT_SQLITE_URL).strip()
        object.__setattr__(self, "DATABASE_URL", normalize_database_url(raw))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Útil em testes após alterar variáveis de ambiente."""
    get_settings.cache_clear()
