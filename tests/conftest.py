"""Banco SQLite temporário (arquivo) para testes — compartilhado entre conexões."""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_tmp_dir = Path(tempfile.mkdtemp(prefix="fm_pytest_"))
_db_file = _tmp_dir / "test.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file.as_posix()}"

from app.core.config import reset_settings_cache  # noqa: E402

reset_settings_cache()

from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _cleanup_temp_db() -> Generator[None, None, None]:
    yield
    shutil.rmtree(_tmp_dir, ignore_errors=True)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def unique_email() -> str:
    return f"user_{uuid.uuid4().hex[:12]}@example.com"


def unique_username() -> str:
    return f"user_{uuid.uuid4().hex[:12]}"


def register_and_token(client: TestClient, password: str = "testpass123") -> tuple[str, str, str]:
    email = unique_email()
    username = unique_username()
    r = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert r.status_code == 201, r.text
    from sqlalchemy import select

    from app.database.connection import SessionLocal
    from app.models.user import AccountStatus, User

    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        user.account_status = AccountStatus.ACTIVE.value
        db.commit()
    finally:
        db.close()
    r2 = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r2.status_code == 200, r2.text
    return email, username, r2.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def setup_year_and_category(client: TestClient, token: str, ano: int = 2026) -> tuple[str, str]:
    h = auth_headers(token)
    client.post("/api/v1/periods/year", json={"ano": ano}, headers=h)
    periods = client.get("/api/v1/periods", headers=h).json()
    period_id = periods[0]["id"]
    cat = client.post(
        "/api/v1/categories",
        json={"nome": "Cat Test", "cor": "#000000", "tipo": "expense"},
        headers=h,
    )
    assert cat.status_code == 201
    return period_id, cat.json()["id"]
