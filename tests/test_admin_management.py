"""Painel admin: estatísticas e logs de erro."""

from tests.conftest import auth_headers, register_and_token
from tests.test_auth import promote_to_admin


def test_admin_management_stats_and_logs(client) -> None:
    admin_email, _, admin_token = register_and_token(client)
    promote_to_admin(admin_email)
    h = auth_headers(admin_token)

    register_and_token(client, password="pass223")

    assert client.get("/api/v1/periods").status_code == 401

    stats = client.get("/api/v1/admin/management/stats", headers=h)
    assert stats.status_code == 200, stats.text
    body = stats.json()
    assert body["total_registered"] >= 2
    assert body["users_ever_logged_in"] >= 1

    logs = client.get("/api/v1/admin/management/error-logs", headers=h)
    assert logs.status_code == 200, logs.text
    assert isinstance(logs.json(), list)
    assert len(logs.json()) >= 1


def test_non_admin_cannot_access_management(client) -> None:
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    assert client.get("/api/v1/admin/management/stats", headers=h).status_code == 403
