"""Cópia de orçamentos do mês anterior."""

from tests.conftest import auth_headers, register_and_token, setup_year_and_category


def test_copy_budgets_from_previous_month(client):
    _, _, token = register_and_token(client)
    period_jan_id, cat_id = setup_year_and_category(client, token, ano=2026)
    h = auth_headers(token)
    periods = client.get("/api/v1/periods", headers=h).json()
    period_feb = next(p for p in periods if p["mes"] == 2 and p["ano"] == 2026)

    r0 = client.post(
        "/api/v1/budgets",
        headers=h,
        json={"categoria_id": cat_id, "period_id": period_jan_id, "valor": "300.00"},
    )
    assert r0.status_code == 201

    r_copy = client.post(
        f"/api/v1/budgets/copy-from-previous?period_id={period_feb['id']}",
        headers=h,
    )
    assert r_copy.status_code == 200
    data = r_copy.json()
    assert len(data) == 1
    assert data[0]["valor"] == "300.00"
    assert data[0]["period_id"] == period_feb["id"]

    r_second = client.post(
        f"/api/v1/budgets/copy-from-previous?period_id={period_feb['id']}",
        headers=h,
    )
    assert r_second.status_code == 200
    assert r_second.json() == []


def test_copy_fails_without_previous_period(client):
    _, _, token = register_and_token(client)
    # só 2026 — janeiro não tem "mês anterior" cadastrado no sistema
    period_jan_id, _cat_id = setup_year_and_category(client, token, ano=2026)
    h = auth_headers(token)
    r = client.post(
        f"/api/v1/budgets/copy-from-previous?period_id={period_jan_id}",
        headers=h,
    )
    assert r.status_code == 400
    assert "anterior" in r.json()["detail"].lower()
