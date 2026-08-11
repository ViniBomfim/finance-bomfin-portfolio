from __future__ import annotations

from decimal import Decimal

from .conftest import auth_headers, register_and_token, setup_year_and_category


def _list_periods_sorted(client, h):
    periods = client.get("/api/v1/periods", headers=h)
    assert periods.status_code == 200, periods.text
    rows = periods.json()
    return sorted(rows, key=lambda p: (p["ano"], p["mes"]))


def _list_card_txs(client, h, card_id: str, period_id: str):
    r = client.get(
        f"/api/v1/card-transactions?card_id={card_id}&period_id={period_id}",
        headers=h,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _shares_total(tx: dict) -> Decimal:
    total = Decimal("0")
    for sh in tx.get("shares", []):
        total += Decimal(str(sh["valor"]))
    return total


def test_edit_shares_in_installment_replicates_to_future_months_only(client) -> None:
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    period_id, cat_id = setup_year_and_category(client, token, ano=2026)
    periods = _list_periods_sorted(client, h)
    jan, feb, mar = periods[0]["id"], periods[1]["id"], periods[2]["id"]
    assert period_id == jan

    c = client.post(
        "/api/v1/cards",
        json={
            "nome": "Cartao Teste",
            "banco": "Banco",
            "limite": "5000.00",
            "fechamento": 10,
            "vencimento": 20,
        },
        headers=h,
    )
    assert c.status_code == 201, c.text
    card_id = c.json()["id"]

    created = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Curso Parcelado",
            "valor": "90.00",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": jan,
            "data": "2026-01-10",
            "pago": False,
            "installment_total": 3,
        },
        headers=h,
    )
    assert created.status_code == 201, created.text

    s1 = client.post("/api/v1/spenders", json={"nome": "Pessoa A"}, headers=h)
    s2 = client.post("/api/v1/spenders", json={"nome": "Pessoa B"}, headers=h)
    assert s1.status_code == 201, s1.text
    assert s2.status_code == 201, s2.text
    spender_1, spender_2 = s1.json()["id"], s2.json()["id"]

    jan_txs = _list_card_txs(client, h, card_id, jan)
    feb_txs = _list_card_txs(client, h, card_id, feb)
    mar_txs = _list_card_txs(client, h, card_id, mar)
    assert len(jan_txs) == len(feb_txs) == len(mar_txs) == 1

    tx_feb_id = feb_txs[0]["id"]
    patch = client.patch(
        f"/api/v1/card-transactions/{tx_feb_id}",
        json={
            "shares": [
                {"spender_id": spender_1, "valor": "10.00"},
                {"spender_id": spender_2, "valor": "20.00"},
            ]
        },
        headers=h,
    )
    assert patch.status_code == 200, patch.text

    jan_after = _list_card_txs(client, h, card_id, jan)[0]
    feb_after = _list_card_txs(client, h, card_id, feb)[0]
    mar_after = _list_card_txs(client, h, card_id, mar)[0]

    assert jan_after["shares"] == []
    assert len(feb_after["shares"]) == 2
    assert len(mar_after["shares"]) == 2
    assert _shares_total(feb_after) == Decimal(str(feb_after["valor"]))
    assert _shares_total(mar_after) == Decimal(str(mar_after["valor"]))


def test_edit_category_in_installment_replicates_to_other_installments(client) -> None:
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

    c = client.post(
        "/api/v1/cards",
        json={
            "nome": "Cartao Teste Categoria",
            "banco": "Banco",
            "limite": "5000.00",
            "fechamento": 10,
            "vencimento": 20,
        },
        headers=h,
    )
    assert c.status_code == 201, c.text
    card_id = c.json()["id"]

    created = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Compra Parcelada Categoria",
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

    assert jan_after["categoria_id"] == cat_b_id
    assert feb_after["categoria_id"] == cat_b_id
    assert mar_after["categoria_id"] == cat_b_id


def test_edit_description_in_installment_replicates_to_other_installments(client) -> None:
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    period_id, cat_id = setup_year_and_category(client, token, ano=2026)
    periods = _list_periods_sorted(client, h)
    jan, feb, mar = periods[0]["id"], periods[1]["id"], periods[2]["id"]
    assert period_id == jan

    c = client.post(
        "/api/v1/cards",
        json={
            "nome": "Cartao Teste Descricao",
            "banco": "Banco",
            "limite": "5000.00",
            "fechamento": 10,
            "vencimento": 20,
        },
        headers=h,
    )
    assert c.status_code == 201, c.text
    card_id = c.json()["id"]

    created = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Compra Parcelada Original",
            "valor": "90.00",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": jan,
            "data": "2026-01-10",
            "pago": False,
            "installment_total": 3,
        },
        headers=h,
    )
    assert created.status_code == 201, created.text

    feb_txs = _list_card_txs(client, h, card_id, feb)
    assert len(feb_txs) == 1
    tx_feb_id = feb_txs[0]["id"]

    patch = client.patch(
        f"/api/v1/card-transactions/{tx_feb_id}",
        json={"descricao": "Compra Parcelada Atualizada"},
        headers=h,
    )
    assert patch.status_code == 200, patch.text

    jan_after = _list_card_txs(client, h, card_id, jan)[0]
    feb_after = _list_card_txs(client, h, card_id, feb)[0]
    mar_after = _list_card_txs(client, h, card_id, mar)[0]

    assert jan_after["descricao"] == "Compra Parcelada Atualizada"
    assert feb_after["descricao"] == "Compra Parcelada Atualizada"
    assert mar_after["descricao"] == "Compra Parcelada Atualizada"

