"""Regressão: duas compras parceladas no mesmo estabelecimento, com o mesmo total de
parcelas mas valores/datas diferentes, não podem se misturar (valor) nem se apagar juntas (delete)."""

from __future__ import annotations

from decimal import Decimal

from .conftest import auth_headers, register_and_token, setup_year_and_category


def _create_card(client, h) -> str:
    c = client.post(
        "/api/v1/cards",
        json={
            "nome": "Cartao Parcelas",
            "banco": "Banco",
            "limite": "10000.00",
            "fechamento": 10,
            "vencimento": 20,
        },
        headers=h,
    )
    assert c.status_code == 201, c.text
    return c.json()["id"]


def _list_txs(client, h, card_id: str, period_id: str) -> list[dict]:
    r = client.get(
        f"/api/v1/card-transactions?card_id={card_id}&period_id={period_id}",
        headers=h,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_distinct_purchases_same_merchant_do_not_merge_or_cascade_delete(client) -> None:
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    period_id, cat_id = setup_year_and_category(client, token, ano=2026)
    card_id = _create_card(client, h)

    # Mesmo estabelecimento, ambas 1/2 e 2/2, porém compras diferentes (valores e datas distintos).
    confirm = client.post(
        "/api/v1/statement-import/confirm",
        json={
            "card_id": card_id,
            "period_id": period_id,
            "creates": [
                {
                    "data": "2026-01-10",
                    "descricao": "Rt Servicos Automotivo",
                    "valor": "259.50",
                    "parcela_atual": 1,
                    "parcela_total": 2,
                    "categoria_id": cat_id,
                },
                {
                    "data": "2026-01-03",
                    "descricao": "Rt Servicos Automotivo",
                    "valor": "600.00",
                    "parcela_atual": 2,
                    "parcela_total": 2,
                    "categoria_id": cat_id,
                },
            ],
        },
        headers=h,
    )
    assert confirm.status_code == 200, confirm.text

    txs = _list_txs(client, h, card_id, period_id)
    # No período atual devem existir exatamente: 1/2 de 259,50 (compra A) e 2/2 de 600,00 (compra B).
    valores = sorted(Decimal(str(t["valor"])) for t in txs)
    assert valores == [Decimal("259.50"), Decimal("600.00")], txs
    # Bug #2: total do período não pode inflar para 1200,00.
    assert sum(valores) == Decimal("859.50")

    # Grupos de parcela distintos: cada compra com seu próprio installment_group_id.
    groups = {t["installment_group_id"] for t in txs}
    assert len(groups) == 2, txs
    assert all(g is not None for g in groups)

    # Bug #1: apagar uma compra não pode apagar a outra.
    tx_b = next(t for t in txs if Decimal(str(t["valor"])) == Decimal("600.00"))
    d = client.delete(f"/api/v1/card-transactions/{tx_b['id']}", headers=h)
    assert d.status_code in (200, 204), d.text

    remaining = _list_txs(client, h, card_id, period_id)
    remaining_vals = [Decimal(str(t["valor"])) for t in remaining]
    assert remaining_vals == [Decimal("259.50")], remaining
