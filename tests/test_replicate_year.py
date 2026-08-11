"""Replicação de orçamentos entre anos."""

from tests.conftest import auth_headers, register_and_token, setup_year_and_category


def test_replicate_budgets_between_years(client):
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    client.post("/api/v1/periods/year", json={"ano": 2026}, headers=h)
    client.post("/api/v1/periods/year", json={"ano": 2027}, headers=h)
    periods = client.get("/api/v1/periods", headers=h).json()
    p_jan_26 = next(p for p in periods if p["mes"] == 1 and p["ano"] == 2026)
    cat = client.post(
        "/api/v1/categories",
        headers=h,
        json={"nome": "Cat Rep", "cor": "#111111", "tipo": "expense"},
    )
    assert cat.status_code == 201
    cat_id = cat.json()["id"]
    assert (
        client.post(
            "/api/v1/budgets",
            headers=h,
            json={"categoria_id": cat_id, "period_id": p_jan_26["id"], "valor": "100.00"},
        ).status_code
        == 201
    )

    r = client.post(
        "/api/v1/budgets/replicate-year",
        headers=h,
        json={"from_ano": 2026, "to_ano": 2027},
    )
    assert r.status_code == 200
    created = r.json()
    assert len(created) >= 1
    p_jan_27 = next(p for p in periods if p["mes"] == 1 and p["ano"] == 2027)
    jan27_budgets = client.get(
        f"/api/v1/budgets?period_id={p_jan_27['id']}",
        headers=h,
    ).json()
    assert len(jan27_budgets) >= 1
