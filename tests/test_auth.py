from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.connection import SessionLocal
from app.models.user import AccountStatus, User
from tests.conftest import auth_headers, register_and_token, unique_email, unique_username


def promote_to_admin(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        user.is_admin = True
        db.add(user)
        db.commit()
    finally:
        db.close()


def test_register_login_me(client: TestClient) -> None:
    email, username, token = register_and_token(client)
    r = client.get("/api/v1/users/me", headers=auth_headers(token))
    assert r.status_code == 200
    assert r.json()["email"] == email
    assert r.json()["username"] == username


def test_login_invalid_password(client: TestClient) -> None:
    email, username, _ = register_and_token(client)
    r = client.post("/api/v1/auth/login", json={"username": username, "password": "wrong"})
    assert r.status_code == 401
    assert email  # used by register


def test_public_register_is_pending_and_blocks_login(client: TestClient) -> None:
    username = unique_username()
    email = unique_email()
    password = "testpass123"
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert reg.status_code == 201, reg.text
    assert reg.json()["username"] == username

    login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert login.status_code == 403
    assert "aprovação" in login.json()["detail"].lower()


def test_admin_approves_access_request(client: TestClient) -> None:
    admin_email, _, admin_token = register_and_token(client, password="adminpass123")
    promote_to_admin(admin_email)

    username = unique_username()
    email = unique_email()
    password = "pendingpass123"
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert reg.status_code == 201
    user_id = reg.json()["id"]

    h = auth_headers(admin_token)
    pending = client.get("/api/v1/users/access-requests", headers=h)
    assert pending.status_code == 200
    assert any(row["id"] == user_id for row in pending.json())

    approve = client.post(f"/api/v1/users/{user_id}/approve", headers=h)
    assert approve.status_code == 204

    login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200

    pending_after = client.get("/api/v1/users/access-requests", headers=h)
    assert not any(row["id"] == user_id for row in pending_after.json())


def test_admin_rejects_access_request(client: TestClient) -> None:
    admin_email, _, admin_token = register_and_token(client)
    promote_to_admin(admin_email)

    username = unique_username()
    email = unique_email()
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": username, "email": email, "password": "rejectme12"},
    )
    assert reg.status_code == 201
    user_id = reg.json()["id"]

    h = auth_headers(admin_token)
    reject = client.post(f"/api/v1/users/{user_id}/reject", headers=h)
    assert reject.status_code == 204

    db = SessionLocal()
    try:
        user = db.get(User, UUID(user_id))
        assert user is None
    finally:
        db.close()


def test_admin_can_list_users_and_reset_password(client: TestClient) -> None:
    admin_email, _, admin_token = register_and_token(client, password="adminpass123")
    user_email, _, _ = register_and_token(client, password="userpass123")
    promote_to_admin(admin_email)

    list_res = client.get("/api/v1/users", headers=auth_headers(admin_token))
    assert list_res.status_code == 200
    assert any(u["email"] == user_email for u in list_res.json())

    user_id = next(u["id"] for u in list_res.json() if u["email"] == user_email)
    reset_res = client.patch(
        f"/api/v1/users/{user_id}/reset-password",
        json={"password": "newpass123"},
        headers=auth_headers(admin_token),
    )
    assert reset_res.status_code == 204

    user_row = next(u for u in list_res.json() if u["email"] == user_email)
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": user_row["username"], "password": "newpass123"},
    )
    assert login_res.status_code == 200


def test_admin_can_create_user_with_free_form_username(client: TestClient) -> None:
    admin_email, _, admin_token = register_and_token(client)
    promote_to_admin(admin_email)
    h = auth_headers(admin_token)

    username = "João Silva"
    email = unique_email()
    r = client.post(
        "/api/v1/users",
        headers=h,
        json={
            "username": username,
            "name": "Usuário Livre",
            "email": email,
            "password": "senha123",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["username"] == username

    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "senha123"},
    )
    assert login.status_code == 200


def test_admin_can_create_user(client: TestClient) -> None:
    admin_email, _, admin_token = register_and_token(client)
    promote_to_admin(admin_email)
    h = auth_headers(admin_token)

    email = unique_email()
    username = unique_username()
    r = client.post(
        "/api/v1/users",
        headers=h,
        json={
            "username": username,
            "name": "Novo Usuário",
            "email": email,
            "password": "senha123",
            "is_admin": False,
            "must_change_password": True,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["email"] == email
    assert r.json()["username"] == username

    dup = client.post(
        "/api/v1/users",
        headers=h,
        json={
            "username": username,
            "name": "Outro",
            "email": email,
            "password": "senha123",
        },
    )
    assert dup.status_code == 409


def test_non_admin_cannot_access_user_management(client: TestClient) -> None:
    _, _, token = register_and_token(client)

    list_res = client.get("/api/v1/users", headers=auth_headers(token))
    assert list_res.status_code == 403

    create_res = client.post(
        "/api/v1/users",
        headers=auth_headers(token),
        json={
            "username": "x_user",
            "name": "X",
            "email": "x@y.com",
            "password": "senha123",
        },
    )
    assert create_res.status_code == 403

    pending_res = client.get("/api/v1/users/access-requests", headers=auth_headers(token))
    assert pending_res.status_code == 403
