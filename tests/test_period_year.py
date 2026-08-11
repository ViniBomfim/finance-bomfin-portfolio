"""Criação idempotente de períodos por ano."""

from tests.conftest import auth_headers, register_and_token


def test_create_year_twice_is_idempotent(client) -> None:
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    ano = 2031
    r1 = client.post("/api/v1/periods/year", json={"ano": ano}, headers=h)
    assert r1.status_code == 200, r1.text
    assert len(r1.json()) == 12
    r2 = client.post("/api/v1/periods/year", json={"ano": ano}, headers=h)
    assert r2.status_code == 200, r2.text
    assert len(r2.json()) == 12
