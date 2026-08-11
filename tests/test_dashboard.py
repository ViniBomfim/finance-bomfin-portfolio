from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_token, setup_year_and_category


def test_dashboard_summary_structure(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    period_id, cat_id = setup_year_and_category(client, token)

    h = auth_headers(token)
    me_sp = client.post("/api/v1/spenders", json={"nome": "EU"}, headers=h)
    assert me_sp.status_code == 201, me_sp.text
    me_spender_id = me_sp.json()["id"]
    patch_me = client.patch("/api/v1/users/me", json={"me_spender_id": me_spender_id}, headers=h)
    assert patch_me.status_code == 200, patch_me.text

    client.post(
        "/api/v1/expenses",
        json={
            "descricao": "Aluguel",
            "valor": "100.00",
            "data": "2026-01-10",
            "period_id": period_id,
            "categoria_id": cat_id,
            "tipo": "fixed",
            "pago": True,
            "shares": [{"spender_id": me_spender_id, "valor": "100.00"}],
        },
        headers=h,
    )

    r = client.get(f"/api/v1/dashboard/summary?period_id={period_id}", headers=h)
    assert r.status_code == 200
    data = r.json()

    assert data["period_id"] == period_id
    assert Decimal(data["total_expenses"]) == Decimal("100")
    assert "monthly_balance" in data
    assert Decimal(data["monthly_balance"]) == Decimal(data["total_income"]) - Decimal(
        data["total_expenses"]
    )

    assert len(data["expenses_by_category"]) >= 1
    row = data["expenses_by_category"][0]
    assert "categoria_id" in row
    assert "categoria_nome" in row
    assert Decimal(row["total"]) == Decimal("100")
    assert isinstance(data["expenses_by_person"], list)
    assert isinstance(data["expenses_by_person_category"], list)

    assert isinstance(data["goal_progress"], list)
    assert isinstance(data["card_totals"], list)
    assert isinstance(data["fixed_expense_lines"], list)
    assert len(data["fixed_expense_lines"]) >= 1
    fixed_row = data["fixed_expense_lines"][0]
    assert "expense_id" in fixed_row
    assert "descricao" in fixed_row
    assert "data" in fixed_row
    assert "categoria_id" in fixed_row
    assert "categoria_nome" in fixed_row
    assert Decimal(fixed_row["valor"]) == Decimal("100")


def test_dashboard_unknown_period_404(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    import uuid

    fake = str(uuid.uuid4())
    r = client.get(f"/api/v1/dashboard/summary?period_id={fake}", headers=auth_headers(token))
    assert r.status_code == 404


def test_dashboard_counts_only_me_share_for_card_totals(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    period_id, cat_id = setup_year_and_category(client, token)
    h = auth_headers(token)

    card = client.post(
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
    assert card.status_code == 201, card.text
    card_id = card.json()["id"]

    me_sp = client.post("/api/v1/spenders", json={"nome": "EU"}, headers=h)
    other_sp = client.post("/api/v1/spenders", json={"nome": "Outro"}, headers=h)
    assert me_sp.status_code == 201, me_sp.text
    assert other_sp.status_code == 201, other_sp.text
    me_spender_id = me_sp.json()["id"]
    other_spender_id = other_sp.json()["id"]

    patch_me = client.patch("/api/v1/users/me", json={"me_spender_id": me_spender_id}, headers=h)
    assert patch_me.status_code == 200, patch_me.text

    # Sem divisão: não deve entrar nas métricas de "EU".
    tx_no_share = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Sem divisao",
            "valor": "100.00",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": period_id,
            "data": "2026-01-10",
            "pago": False,
            "installment_total": 1,
            "shares": [],
        },
        headers=h,
    )
    assert tx_no_share.status_code == 201, tx_no_share.text

    # Com divisão: entra apenas a parte do "EU" (30,00).
    tx_with_share = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Com divisao",
            "valor": "100.00",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": period_id,
            "data": "2026-01-11",
            "pago": False,
            "installment_total": 1,
            "shares": [
                {"spender_id": me_spender_id, "valor": "30.00"},
                {"spender_id": other_spender_id, "valor": "70.00"},
            ],
        },
        headers=h,
    )
    assert tx_with_share.status_code == 201, tx_with_share.text

    r = client.get(f"/api/v1/dashboard/summary?period_id={period_id}", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert Decimal(data["total_expenses"]) == Decimal("30.00")
    assert Decimal(data["pending_expenses"]) == Decimal("30.00")


def test_dashboard_counts_only_me_share_for_fixed_expenses(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    period_id, cat_id = setup_year_and_category(client, token)
    h = auth_headers(token)

    me_sp = client.post("/api/v1/spenders", json={"nome": "EU"}, headers=h)
    other_sp = client.post("/api/v1/spenders", json={"nome": "Outro"}, headers=h)
    assert me_sp.status_code == 201, me_sp.text
    assert other_sp.status_code == 201, other_sp.text
    me_spender_id = me_sp.json()["id"]
    other_spender_id = other_sp.json()["id"]
    patch_me = client.patch("/api/v1/users/me", json={"me_spender_id": me_spender_id}, headers=h)
    assert patch_me.status_code == 200, patch_me.text

    # Sem divisão: não deve entrar nas métricas de "EU".
    expense_no_share = client.post(
        "/api/v1/expenses",
        json={
            "descricao": "Internet sem divisão",
            "valor": "100.00",
            "data": "2026-01-10",
            "period_id": period_id,
            "categoria_id": cat_id,
            "tipo": "fixed",
            "pago": False,
        },
        headers=h,
    )
    assert expense_no_share.status_code == 201, expense_no_share.text

    # Com divisão: entra apenas a parte do "EU" (35,00).
    expense_with_share = client.post(
        "/api/v1/expenses",
        json={
            "descricao": "Internet com divisão",
            "valor": "100.00",
            "data": "2026-01-11",
            "period_id": period_id,
            "categoria_id": cat_id,
            "tipo": "fixed",
            "pago": False,
            "shares": [
                {"spender_id": me_spender_id, "valor": "35.00"},
                {"spender_id": other_spender_id, "valor": "65.00"},
            ],
        },
        headers=h,
    )
    assert expense_with_share.status_code == 201, expense_with_share.text

    r = client.get(f"/api/v1/dashboard/summary?period_id={period_id}", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert Decimal(data["total_expenses"]) == Decimal("35.00")
    assert Decimal(data["pending_expenses"]) == Decimal("35.00")


def test_dashboard_debtors_include_only_explicit_spender_association(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    period_id, _ = setup_year_and_category(client, token)
    h = auth_headers(token)

    spender = client.post("/api/v1/spenders", json={"nome": "Maria Cartao"}, headers=h)
    assert spender.status_code == 201, spender.text
    spender_id = spender.json()["id"]

    linked = client.post(
        "/api/v1/debtors",
        headers=h,
        json={
            "devedor_nome": "Maria",
            "valor_emprestado": "200.00",
            "data_emprestimo": "2026-01-10",
            "destino_dinheiro": "Meta de viagem",
            "spender_id": spender_id,
        },
    )
    assert linked.status_code == 201, linked.text

    unlinked = client.post(
        "/api/v1/debtors",
        headers=h,
        json={
            "devedor_nome": "Maria",
            "valor_emprestado": "150.00",
            "data_emprestimo": "2026-01-11",
            "destino_dinheiro": "Reserva geral",
        },
    )
    assert unlinked.status_code == 201, unlinked.text

    r = client.get(f"/api/v1/dashboard/summary?period_id={period_id}", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()

    person_row = next((row for row in data["usage_by_person_cards"] if row["pessoa_id"] == spender_id), None)
    assert person_row is not None
    assert Decimal(person_row["total_divida_devedores"]) == Decimal("200.00")
    assert len(person_row["devedores"]) == 1
    assert person_row["devedores"][0]["loan_id"] == linked.json()["id"]
    assert person_row["devedores"][0]["spender_id"] == spender_id
