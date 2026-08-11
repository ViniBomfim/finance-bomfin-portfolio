from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_token, setup_year_and_category


def test_expense_crud_and_list_by_period(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    period_id, cat_id = setup_year_and_category(client, token)
    h = auth_headers(token)

    r = client.post(
        "/api/v1/expenses",
        json={
            "descricao": "Teste",
            "valor": "50.25",
            "data": "2026-03-15",
            "period_id": period_id,
            "categoria_id": cat_id,
            "tipo": "variable",
            "pago": False,
        },
        headers=h,
    )
    assert r.status_code == 201
    eid = r.json()["id"]
    assert r.json()["tipo"] == "variable"

    r2 = client.get(f"/api/v1/expenses/{eid}", headers=h)
    assert r2.status_code == 200
    assert r2.json()["valor"] == "50.25"

    listed = client.get(f"/api/v1/expenses?period_id={period_id}", headers=h).json()
    assert len(listed) == 1

    r3 = client.delete(f"/api/v1/expenses/{eid}", headers=h)
    assert r3.status_code == 204


def test_list_expenses_requires_filter(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    r = client.get("/api/v1/expenses", headers=auth_headers(token))
    assert r.status_code == 400
    msg = str(r.json().get("detail", "")).lower()
    assert "period_id" in msg or "categoria" in msg


def test_fixed_recurring_allows_blank_or_same_value_on_future_months(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    period_id, cat_id = setup_year_and_category(client, token)
    h = auth_headers(token)

    same_resp = client.post(
        "/api/v1/expenses",
        json={
            "descricao": "Internet Casa",
            "valor": "150.00",
            "data": "2026-01-10",
            "period_id": period_id,
            "categoria_id": cat_id,
            "tipo": "fixed",
            "recorrente": True,
            "pago": False,
            "recurrence_value_mode": "same_value",
        },
        headers=h,
    )
    assert same_resp.status_code == 201, same_resp.text

    blank_resp = client.post(
        "/api/v1/expenses",
        json={
            "descricao": "Academia",
            "valor": "120.00",
            "data": "2026-01-12",
            "period_id": period_id,
            "categoria_id": cat_id,
            "tipo": "fixed",
            "recorrente": True,
            "pago": False,
            "recurrence_value_mode": "blank",
        },
        headers=h,
    )
    assert blank_resp.status_code == 201, blank_resp.text

    rows = client.get(f"/api/v1/expenses?categoria_id={cat_id}", headers=h).json()
    internet_rows = [x for x in rows if x["descricao"] == "Internet Casa"]
    academia_rows = [x for x in rows if x["descricao"] == "Academia"]

    assert len(internet_rows) >= 2
    assert len(academia_rows) >= 2

    internet_future = [x for x in internet_rows if x["period_id"] != period_id]
    academia_future = [x for x in academia_rows if x["period_id"] != period_id]

    assert internet_future
    assert academia_future
    assert all(x["valor"] == "150.00" for x in internet_future)
    assert all(x["valor"] == "0.00" for x in academia_future)


def test_fixed_recurring_on_update_replicates_future_months(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    period_id, cat_id = setup_year_and_category(client, token)
    h = auth_headers(token)
    periods = client.get("/api/v1/periods", headers=h).json()
    jan = next(p for p in periods if p["mes"] == 1)
    feb = next(p for p in periods if p["mes"] == 2)

    create_resp = client.post(
        "/api/v1/expenses",
        json={
            "descricao": "Aluguel",
            "valor": "2000.00",
            "data": "2026-01-05",
            "period_id": jan["id"],
            "categoria_id": cat_id,
            "tipo": "fixed",
            "recorrente": False,
            "pago": False,
        },
        headers=h,
    )
    assert create_resp.status_code == 201, create_resp.text
    eid = create_resp.json()["id"]

    feb_before = client.get(f"/api/v1/expenses?period_id={feb['id']}", headers=h).json()
    assert not [x for x in feb_before if x["descricao"] == "Aluguel"]

    patch_resp = client.patch(
        f"/api/v1/expenses/{eid}",
        json={"recorrente": True},
        headers=h,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["recorrente"] is True

    feb_after = client.get(f"/api/v1/expenses?period_id={feb['id']}", headers=h).json()
    aluguel_feb = [x for x in feb_after if x["descricao"] == "Aluguel"]
    assert len(aluguel_feb) == 1
    assert aluguel_feb[0]["valor"] == "2000.00"
    assert aluguel_feb[0]["recorrente"] is False

    patch_again = client.patch(
        f"/api/v1/expenses/{eid}",
        json={"recorrente": True, "descricao": "Aluguel"},
        headers=h,
    )
    assert patch_again.status_code == 200, patch_again.text

    feb_final = client.get(f"/api/v1/expenses?period_id={feb['id']}", headers=h).json()
    assert len([x for x in feb_final if x["descricao"] == "Aluguel"]) == 1


def test_update_valor_scales_existing_shares(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    period_id, cat_id = setup_year_and_category(client, token)
    h = auth_headers(token)

    s_a = client.post("/api/v1/spenders", json={"nome": "Ana"}, headers=h)
    s_b = client.post("/api/v1/spenders", json={"nome": "Bruno"}, headers=h)
    assert s_a.status_code == 201, s_a.text
    assert s_b.status_code == 201, s_b.text
    spender_a = s_a.json()["id"]
    spender_b = s_b.json()["id"]

    create_resp = client.post(
        "/api/v1/expenses",
        json={
            "descricao": "Condomínio",
            "valor": "100.00",
            "data": "2026-01-10",
            "period_id": period_id,
            "categoria_id": cat_id,
            "tipo": "fixed",
            "pago": False,
            "shares": [
                {"spender_id": spender_a, "valor": "50.00"},
                {"spender_id": spender_b, "valor": "50.00"},
            ],
        },
        headers=h,
    )
    assert create_resp.status_code == 201, create_resp.text
    eid = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/v1/expenses/{eid}",
        json={"valor": "150.00"},
        headers=h,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["valor"] == "150.00"

    shares = patch_resp.json()["shares"]
    assert len(shares) == 2
    total = sum(Decimal(sh["valor"]) for sh in shares)
    assert total == Decimal("150.00")
    by_spender = {sh["spender_id"]: Decimal(sh["valor"]) for sh in shares}
    assert by_spender[spender_a] == Decimal("75.00")
    assert by_spender[spender_b] == Decimal("75.00")


def test_expense_share_paid_toggle_partial_and_mark_all(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    period_id, cat_id = setup_year_and_category(client, token)
    h = auth_headers(token)

    s_a = client.post("/api/v1/spenders", json={"nome": "Ana"}, headers=h)
    s_b = client.post("/api/v1/spenders", json={"nome": "Bruno"}, headers=h)
    assert s_a.status_code == 201, s_a.text
    assert s_b.status_code == 201, s_b.text
    spender_a = s_a.json()["id"]
    spender_b = s_b.json()["id"]

    create_resp = client.post(
        "/api/v1/expenses",
        json={
            "descricao": "Conta 1",
            "valor": "300.00",
            "data": "2026-01-15",
            "period_id": period_id,
            "categoria_id": cat_id,
            "tipo": "fixed",
            "pago": False,
            "shares": [
                {"spender_id": spender_a, "valor": "150.00"},
                {"spender_id": spender_b, "valor": "150.00"},
            ],
        },
        headers=h,
    )
    assert create_resp.status_code == 201, create_resp.text
    body = create_resp.json()
    eid = body["id"]
    assert body["pago"] is False
    assert all(sh["pago"] is False for sh in body["shares"])

    partial = client.post(
        f"/api/v1/expenses/{eid}/shares/{spender_a}/paid?pago=true",
        headers=h,
    )
    assert partial.status_code == 200, partial.text
    partial_body = partial.json()
    assert partial_body["pago"] is False
    by_spender = {sh["spender_id"]: sh["pago"] for sh in partial_body["shares"]}
    assert by_spender[spender_a] is True
    assert by_spender[spender_b] is False

    mark_all = client.post(f"/api/v1/expenses/{eid}/paid?pago=true", headers=h)
    assert mark_all.status_code == 200, mark_all.text
    all_body = mark_all.json()
    assert all_body["pago"] is True
    assert all(sh["pago"] is True for sh in all_body["shares"])

    unmark_one = client.post(
        f"/api/v1/expenses/{eid}/shares/{spender_b}/paid?pago=false",
        headers=h,
    )
    assert unmark_one.status_code == 200, unmark_one.text
    unmark_body = unmark_one.json()
    assert unmark_body["pago"] is False
    by_spender = {sh["spender_id"]: sh["pago"] for sh in unmark_body["shares"]}
    assert by_spender[spender_a] is True
    assert by_spender[spender_b] is False

    unmark_all = client.post(f"/api/v1/expenses/{eid}/paid?pago=false", headers=h)
    assert unmark_all.status_code == 200, unmark_all.text
    assert unmark_all.json()["pago"] is False
    assert all(sh["pago"] is False for sh in unmark_all.json()["shares"])
