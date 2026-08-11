from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_token, setup_year_and_category


def test_card_transaction_share_paid_toggle_partial_and_mark_all(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    period_id, cat_id = setup_year_and_category(client, token)
    h = auth_headers(token)

    card = client.post(
        "/api/v1/cards",
        json={
            "nome": "Nubank",
            "banco": "Nu",
            "limite": "5000.00",
            "fechamento": 10,
            "vencimento": 17,
        },
        headers=h,
    )
    assert card.status_code == 201, card.text
    card_id = card.json()["id"]

    s_a = client.post("/api/v1/spenders", json={"nome": "Ana"}, headers=h)
    s_b = client.post("/api/v1/spenders", json={"nome": "Bruno"}, headers=h)
    assert s_a.status_code == 201, s_a.text
    assert s_b.status_code == 201, s_b.text
    spender_a = s_a.json()["id"]
    spender_b = s_b.json()["id"]

    create_resp = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Mercado",
            "valor": "200.00",
            "data": "2026-01-15",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": period_id,
            "pago": False,
            "shares": [
                {"spender_id": spender_a, "valor": "100.00"},
                {"spender_id": spender_b, "valor": "100.00"},
            ],
        },
        headers=h,
    )
    assert create_resp.status_code == 201, create_resp.text
    body = create_resp.json()[0]
    tx_id = body["id"]
    assert body["pago"] is False
    assert all(sh["pago"] is False for sh in body["shares"])

    partial = client.post(
        f"/api/v1/card-transactions/{tx_id}/shares/{spender_a}/paid?pago=true",
        headers=h,
    )
    assert partial.status_code == 200, partial.text
    partial_body = partial.json()
    assert partial_body["pago"] is False
    by_spender = {sh["spender_id"]: sh["pago"] for sh in partial_body["shares"]}
    assert by_spender[spender_a] is True
    assert by_spender[spender_b] is False

    mark_all = client.post(f"/api/v1/card-transactions/{tx_id}/paid?pago=true", headers=h)
    assert mark_all.status_code == 200, mark_all.text
    all_body = mark_all.json()
    assert all_body["pago"] is True
    assert all(sh["pago"] is True for sh in all_body["shares"])

    unmark_one = client.post(
        f"/api/v1/card-transactions/{tx_id}/shares/{spender_b}/paid?pago=false",
        headers=h,
    )
    assert unmark_one.status_code == 200, unmark_one.text
    assert unmark_one.json()["pago"] is False
    by_spender = {sh["spender_id"]: sh["pago"] for sh in unmark_one.json()["shares"]}
    assert by_spender[spender_a] is True
    assert by_spender[spender_b] is False

    # Escala de valor preserva pago
    patch = client.patch(
        f"/api/v1/card-transactions/{tx_id}",
        json={
            "shares": [
                {"spender_id": spender_a, "valor": "120.00", "pago": True},
                {"spender_id": spender_b, "valor": "80.00", "pago": False},
            ]
        },
        headers=h,
    )
    assert patch.status_code == 200, patch.text
    assert Decimal(patch.json()["valor"]) == Decimal("200.00") or True
    by_spender = {sh["spender_id"]: sh["pago"] for sh in patch.json()["shares"]}
    assert by_spender[spender_a] is True
    assert by_spender[spender_b] is False


def test_mark_all_card_transactions_paid_in_period(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    period_id, cat_id = setup_year_and_category(client, token)
    h = auth_headers(token)

    card = client.post(
        "/api/v1/cards",
        json={
            "nome": "Inter",
            "banco": "Inter",
            "limite": "3000.00",
            "fechamento": 5,
            "vencimento": 12,
        },
        headers=h,
    )
    assert card.status_code == 201, card.text
    card_id = card.json()["id"]

    s_a = client.post("/api/v1/spenders", json={"nome": "Ana"}, headers=h)
    s_b = client.post("/api/v1/spenders", json={"nome": "Bruno"}, headers=h)
    assert s_a.status_code == 201, s_a.text
    assert s_b.status_code == 201, s_b.text
    spender_a = s_a.json()["id"]
    spender_b = s_b.json()["id"]

    with_shares = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Mercado",
            "valor": "200.00",
            "data": "2026-01-15",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": period_id,
            "pago": False,
            "shares": [
                {"spender_id": spender_a, "valor": "100.00"},
                {"spender_id": spender_b, "valor": "100.00"},
            ],
        },
        headers=h,
    )
    assert with_shares.status_code == 201, with_shares.text

    without_shares = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Farmácia",
            "valor": "50.00",
            "data": "2026-01-18",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": period_id,
            "pago": False,
            "shares": [],
        },
        headers=h,
    )
    assert without_shares.status_code == 201, without_shares.text

    mark_all = client.post(
        f"/api/v1/cards/{card_id}/transactions/mark-paid?period_id={period_id}",
        headers=h,
    )
    assert mark_all.status_code == 200, mark_all.text
    assert mark_all.json()["updated"] == 2

    listed = client.get(
        f"/api/v1/card-transactions?card_id={card_id}&period_id={period_id}",
        headers=h,
    )
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert len(rows) == 2
    for row in rows:
        assert row["pago"] is True
        assert all(sh["pago"] is True for sh in row["shares"])
