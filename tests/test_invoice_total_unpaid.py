from datetime import date

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_token, setup_year_and_category


def test_invoice_total_unpaid_and_paid_at(client: TestClient) -> None:
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

    empty = client.get(
        f"/api/v1/card-transactions/invoice-total?card_id={card_id}&period_id={period_id}",
        headers=h,
    )
    assert empty.status_code == 200, empty.text
    empty_body = empty.json()
    assert empty_body["unpaid_count"] == 0
    assert float(empty_body["unpaid_total"]) == 0.0
    assert empty_body["paid_at"] is None

    create_a = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Mercado",
            "valor": "100.00",
            "data": "2026-01-10",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": period_id,
            "pago": False,
        },
        headers=h,
    )
    assert create_a.status_code == 201, create_a.text
    tx_a = create_a.json()[0]["id"]

    create_b = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Farmácia",
            "valor": "50.00",
            "data": "2026-01-12",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": period_id,
            "pago": False,
        },
        headers=h,
    )
    assert create_b.status_code == 201, create_b.text
    tx_b = create_b.json()[0]["id"]

    pending = client.get(
        f"/api/v1/card-transactions/invoice-total?card_id={card_id}&period_id={period_id}",
        headers=h,
    )
    assert pending.status_code == 200, pending.text
    pending_body = pending.json()
    assert pending_body["unpaid_count"] == 2
    assert float(pending_body["unpaid_total"]) == 150.0
    assert pending_body["paid_at"] is None

    mark_a = client.post(f"/api/v1/card-transactions/{tx_a}/paid?pago=true", headers=h)
    assert mark_a.status_code == 200, mark_a.text

    partial = client.get(
        f"/api/v1/card-transactions/invoice-total?card_id={card_id}&period_id={period_id}",
        headers=h,
    )
    assert partial.status_code == 200, partial.text
    partial_body = partial.json()
    assert partial_body["unpaid_count"] == 1
    assert float(partial_body["unpaid_total"]) == 50.0
    assert partial_body["paid_at"] is None

    mark_b = client.post(f"/api/v1/card-transactions/{tx_b}/paid?pago=true", headers=h)
    assert mark_b.status_code == 200, mark_b.text

    paid = client.get(
        f"/api/v1/card-transactions/invoice-total?card_id={card_id}&period_id={period_id}",
        headers=h,
    )
    assert paid.status_code == 200, paid.text
    paid_body = paid.json()
    assert paid_body["unpaid_count"] == 0
    assert float(paid_body["unpaid_total"]) == 0.0
    assert paid_body["paid_at"] == date.today().isoformat()
