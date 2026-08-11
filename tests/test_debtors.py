from decimal import Decimal

from tests.conftest import auth_headers, register_and_token


def _to_decimal(value: str | float | int) -> Decimal:
    return Decimal(str(value))


def test_debtor_partial_payment_and_settlement_flow(client):
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    spender = client.post("/api/v1/spenders", headers=h, json={"nome": "Carlos Cartao"})
    assert spender.status_code == 201, spender.text
    spender_id = spender.json()["id"]

    create = client.post(
        "/api/v1/debtors",
        headers=h,
        json={
            "devedor_nome": "Carlos",
            "valor_emprestado": "150.00",
            "data_emprestimo": "2026-04-10",
            "destino_dinheiro": "Investir na reserva",
            "observacoes": "Emprestimo por fora",
            "spender_id": spender_id,
        },
    )
    assert create.status_code == 201, create.text
    loan = create.json()
    assert loan["devedor_nome"] == "Carlos"
    assert loan["status"] == "pendente"
    assert loan["spender_id"] == spender_id
    assert loan["spender_nome"] == "Carlos Cartao"
    assert _to_decimal(loan["valor_pago"]) == Decimal("0.00")
    assert _to_decimal(loan["valor_restante"]) == Decimal("150.00")
    assert loan["ultimo_pagamento_em"] is None
    assert isinstance(loan["dias_sem_pagamento"], int)
    assert loan["pagamentos"] == []

    p1 = client.post(
        f"/api/v1/debtors/{loan['id']}/payments",
        headers=h,
        json={
            "data_pagamento": "2026-04-12",
            "valor_pago": "40.00",
            "observacao": "Primeira parte",
        },
    )
    assert p1.status_code == 200, p1.text
    after_p1 = p1.json()
    assert _to_decimal(after_p1["valor_pago"]) == Decimal("40.00")
    assert _to_decimal(after_p1["valor_restante"]) == Decimal("110.00")
    assert after_p1["status"] == "pendente"
    assert after_p1["ultimo_pagamento_em"] == "2026-04-12"
    assert isinstance(after_p1["dias_sem_pagamento"], int)
    assert len(after_p1["pagamentos"]) == 1

    p2 = client.post(
        f"/api/v1/debtors/{loan['id']}/payments",
        headers=h,
        json={
            "data_pagamento": "2026-04-15",
            "valor_pago": "110.00",
            "observacao": "Quitacao",
        },
    )
    assert p2.status_code == 200, p2.text
    settled = p2.json()
    assert _to_decimal(settled["valor_pago"]) == Decimal("150.00")
    assert _to_decimal(settled["valor_restante"]) == Decimal("0.00")
    assert settled["status"] == "quitado"
    assert settled["ultimo_pagamento_em"] == "2026-04-15"
    assert isinstance(settled["dias_sem_pagamento"], int)


def test_debtor_rejects_payment_above_remaining(client):
    _, _, token = register_and_token(client)
    h = auth_headers(token)

    create = client.post(
        "/api/v1/debtors",
        headers=h,
        json={
            "devedor_nome": "Maria",
            "valor_emprestado": "100.00",
            "data_emprestimo": "2026-04-05",
            "destino_dinheiro": "Pagar fatura",
        },
    )
    assert create.status_code == 201, create.text
    loan_id = create.json()["id"]

    over = client.post(
        f"/api/v1/debtors/{loan_id}/payments",
        headers=h,
        json={
            "data_pagamento": "2026-04-06",
            "valor_pago": "120.00",
        },
    )
    assert over.status_code == 400
    assert "excede" in over.json()["detail"].lower()


def test_debtor_rejects_spender_from_other_user(client):
    _, _, token_a = register_and_token(client)
    h_a = auth_headers(token_a)
    _, _, token_b = register_and_token(client)
    h_b = auth_headers(token_b)

    spender_b = client.post("/api/v1/spenders", headers=h_b, json={"nome": "Pessoa B"})
    assert spender_b.status_code == 201, spender_b.text
    foreign_spender_id = spender_b.json()["id"]

    create = client.post(
        "/api/v1/debtors",
        headers=h_a,
        json={
            "devedor_nome": "Carlos",
            "valor_emprestado": "80.00",
            "data_emprestimo": "2026-04-03",
            "destino_dinheiro": "Cobrir caixa",
            "spender_id": foreign_spender_id,
        },
    )
    assert create.status_code == 400
    assert "inválida" in create.json()["detail"].lower() or "invalida" in create.json()["detail"].lower()
