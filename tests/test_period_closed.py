"""Período fechado bloqueia mutações diretas, mas não aborta operações em meses abertos."""

from __future__ import annotations

from decimal import Decimal

from tests.conftest import auth_headers, register_and_token, setup_year_and_category


def _list_periods_sorted(client, h):
    periods = client.get("/api/v1/periods", headers=h)
    assert periods.status_code == 200, periods.text
    return sorted(periods.json(), key=lambda p: (p["ano"], p["mes"]))


def _list_card_txs(client, h, card_id: str, period_id: str) -> list[dict]:
    r = client.get(
        f"/api/v1/card-transactions?card_id={card_id}&period_id={period_id}",
        headers=h,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _create_card(client, h) -> str:
    c = client.post(
        "/api/v1/cards",
        json={
            "nome": "Cartao Periodo Fechado",
            "banco": "Banco",
            "limite": "5000.00",
            "fechamento": 10,
            "vencimento": 20,
        },
        headers=h,
    )
    assert c.status_code == 201, c.text
    return c.json()["id"]


def test_expense_rejected_when_period_closed(client):
    _, _, token = register_and_token(client)
    period_id, cat_id = setup_year_and_category(client, token)

    h = auth_headers(token)
    r_close = client.post(f"/api/v1/periods/{period_id}/close", headers=h)
    assert r_close.status_code == 200

    r = client.post(
        "/api/v1/expenses",
        headers=h,
        json={
            "descricao": "Test",
            "valor": "100.00",
            "data": "2026-03-15",
            "tipo": "variable",
            "pago": False,
            "period_id": period_id,
            "categoria_id": cat_id,
        },
    )
    assert r.status_code == 400
    assert "fechado" in r.json()["detail"].lower()


def test_reopen_period_allows_expense_again(client):
    _, _, token = register_and_token(client)
    period_id, cat_id = setup_year_and_category(client, token)
    h = auth_headers(token)

    assert client.post(f"/api/v1/periods/{period_id}/close", headers=h).status_code == 200
    assert client.post(f"/api/v1/periods/{period_id}/open", headers=h).status_code == 200

    r = client.post(
        "/api/v1/expenses",
        headers=h,
        json={
            "descricao": "After reopen",
            "valor": "50.00",
            "data": "2026-04-10",
            "tipo": "variable",
            "pago": False,
            "period_id": period_id,
            "categoria_id": cat_id,
        },
    )
    assert r.status_code == 201


def test_edit_installment_skips_closed_sibling_periods(client):
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    period_id, cat_a_id = setup_year_and_category(client, token, ano=2026)
    periods = _list_periods_sorted(client, h)
    jan, feb, mar = periods[0]["id"], periods[1]["id"], periods[2]["id"]
    assert period_id == jan

    cat_b = client.post(
        "/api/v1/categories",
        json={"nome": "Outra categoria", "cor": "#123456", "tipo": "expense"},
        headers=h,
    )
    assert cat_b.status_code == 201, cat_b.text
    cat_b_id = cat_b.json()["id"]

    card_id = _create_card(client, h)
    created = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Compra Parcelada",
            "valor": "90.00",
            "card_id": card_id,
            "categoria_id": cat_a_id,
            "period_id": jan,
            "data": "2026-01-10",
            "pago": False,
            "installment_total": 3,
        },
        headers=h,
    )
    assert created.status_code == 201, created.text

    assert client.post(f"/api/v1/periods/{jan}/close", headers=h).status_code == 200

    feb_txs = _list_card_txs(client, h, card_id, feb)
    assert len(feb_txs) == 1
    tx_feb_id = feb_txs[0]["id"]

    patch = client.patch(
        f"/api/v1/card-transactions/{tx_feb_id}",
        json={"categoria_id": cat_b_id},
        headers=h,
    )
    assert patch.status_code == 200, patch.text

    jan_after = _list_card_txs(client, h, card_id, jan)[0]
    feb_after = _list_card_txs(client, h, card_id, feb)[0]
    mar_after = _list_card_txs(client, h, card_id, mar)[0]

    assert jan_after["categoria_id"] == cat_a_id
    assert feb_after["categoria_id"] == cat_b_id
    assert mar_after["categoria_id"] == cat_b_id


def test_import_confirm_skips_updates_in_closed_period(client):
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    period_id, cat_id = setup_year_and_category(client, token, ano=2026)
    periods = _list_periods_sorted(client, h)
    jan, feb = periods[0]["id"], periods[1]["id"]
    card_id = _create_card(client, h)

    created = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Loja Antiga",
            "valor": "100.00",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": jan,
            "data": "2026-01-15",
            "pago": False,
            "from_statement": True,
        },
        headers=h,
    )
    assert created.status_code == 201, created.text
    jan_tx_id = created.json()[0]["id"]

    assert client.post(f"/api/v1/periods/{jan}/close", headers=h).status_code == 200

    confirm = client.post(
        "/api/v1/statement-import/confirm",
        json={
            "card_id": card_id,
            "period_id": feb,
            "creates": [
                {
                    "data": "2026-02-10",
                    "descricao": "Compra Nova",
                    "valor": "50.00",
                    "categoria_id": cat_id,
                }
            ],
            "updates": [
                {
                    "transaction_id": jan_tx_id,
                    "apply": True,
                    "valor": "120.00",
                }
            ],
        },
        headers=h,
    )
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()
    assert body["created"] == 1
    assert body["updated"] == 0

    jan_after = _list_card_txs(client, h, card_id, jan)[0]
    feb_txs = _list_card_txs(client, h, card_id, feb)
    assert Decimal(str(jan_after["valor"])) == Decimal("100.00")
    assert len(feb_txs) == 1
    assert Decimal(str(feb_txs[0]["valor"])) == Decimal("50.00")


def test_delete_all_months_preserves_closed_periods(client):
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    period_id, cat_id = setup_year_and_category(client, token, ano=2026)
    periods = _list_periods_sorted(client, h)
    jan, feb = periods[0]["id"], periods[1]["id"]
    card_id = _create_card(client, h)

    for pid, desc, data in (
        (jan, "Jan Tx", "2026-01-10"),
        (feb, "Fev Tx", "2026-02-10"),
    ):
        r = client.post(
            "/api/v1/card-transactions",
            json={
                "descricao": desc,
                "valor": "80.00",
                "card_id": card_id,
                "categoria_id": cat_id,
                "period_id": pid,
                "data": data,
                "pago": False,
            },
            headers=h,
        )
        assert r.status_code == 201, r.text

    assert client.post(f"/api/v1/periods/{jan}/close", headers=h).status_code == 200

    deleted = client.delete(f"/api/v1/cards/{card_id}/transactions/all-months", headers=h)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] == 1

    assert len(_list_card_txs(client, h, card_id, jan)) == 1
    assert len(_list_card_txs(client, h, card_id, feb)) == 0
