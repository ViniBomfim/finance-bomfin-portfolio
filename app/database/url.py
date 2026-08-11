"""Normalização de URLs de banco (SQLite local, PostgreSQL / Supabase)."""

from __future__ import annotations

from urllib.parse import quote_plus

DEFAULT_SQLITE_URL = "sqlite:///./finance_manager.db"


def normalize_database_url(url: str) -> str:
    """Garante driver psycopg2, credenciais codificadas e SSL para Supabase."""
    raw = _encode_postgres_credentials(url.strip())
    if raw.startswith("postgres://"):
        raw = "postgresql+psycopg2://" + raw[len("postgres://") :]
    elif raw.startswith("postgresql://") and not raw.startswith("postgresql+"):
        raw = "postgresql+psycopg2://" + raw[len("postgresql://") :]

    if _is_postgresql_url(raw):
        separator = "&" if "?" in raw else "?"
        if "sslmode=" not in raw:
            raw = f"{raw}{separator}sslmode=require"
            separator = "&"
        # Evita hang infinito no Render quando Supabase está pausado/inacessível.
        if "connect_timeout=" not in raw:
            raw = f"{raw}{separator}connect_timeout=15"

    return raw


def _encode_postgres_credentials(url: str) -> str:
    """Codifica senha quando contém @, /, ? etc. (comum em URIs coladas no .env)."""
    if not _is_postgresql_url(url):
        return url

    scheme_end = url.find("://")
    if scheme_end == -1:
        return url

    scheme = url[: scheme_end + 3]
    rest = url[scheme_end + 3 :]
    query = ""
    if "?" in rest:
        rest, query = rest.split("?", 1)
        query = f"?{query}"

    at = rest.rfind("@")
    if at == -1:
        return url

    userinfo = rest[:at]
    hostpart = rest[at + 1 :]
    colon = userinfo.find(":")
    if colon == -1:
        return url

    user = userinfo[:colon]
    password = userinfo[colon + 1 :]
    # Já codificada (ex.: %40) — não codificar de novo.
    if password == quote_plus(password, safe=""):
        return url

    encoded_password = quote_plus(password, safe="")
    return f"{scheme}{user}:{encoded_password}@{hostpart}{query}"


def is_postgresql_url(url: str) -> bool:
    return _is_postgresql_url(url.strip())


def _is_postgresql_url(url: str) -> bool:
    lowered = url.lower()
    return lowered.startswith("postgresql") or lowered.startswith("postgres://")
