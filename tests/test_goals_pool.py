from decimal import Decimal

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_token


def _setup_meta_pool(client: TestClient, token: str, pool_amount: str = "500.00") -> tuple[dict[str, str], str, str]:
    h = auth_headers(token)
    client.post("/api/v1/periods/year", json={"ano": 2026}, headers=h)
    periods = client.get("/api/v1/periods", headers=h).json()
    period_id = periods[0]["id"]

    meta_cat = client.post(
        "/api/v1/categories",
        json={"nome": "Metas reserva", "cor": "#00ff00", "tipo": "expense"},
        headers=h,
    )
    assert meta_cat.status_code == 201, meta_cat.text
    meta_cat_id = meta_cat.json()["id"]

    income_cat = client.post(
        "/api/v1/categories",
        json={"nome": "Salário", "cor": "#0000ff", "tipo": "income"},
        headers=h,
    )
    assert income_cat.status_code == 201, income_cat.text
    income_cat_id = income_cat.json()["id"]

    exp = client.post(
        "/api/v1/expenses",
        json={
            "descricao": "Reserva metas",
            "valor": pool_amount,
            "data": "2026-01-15",
            "period_id": period_id,
            "categoria_id": meta_cat_id,
            "tipo": "fixed",
            "pago": True,
        },
        headers=h,
    )
    assert exp.status_code == 201, exp.text
    return h, period_id, income_cat_id


def _create_goal(client: TestClient, h: dict[str, str]) -> str:
    r = client.post(
        "/api/v1/goals",
        json={
            "nome": "Viagem",
            "tipo": "short",
            "valor_meta": "1000",
            "data_inicio": "2026-01-01",
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _pool_summary(client: TestClient, h: dict[str, str], period_id: str) -> dict[str, str]:
    r = client.get(f"/api/v1/goals/pool-summary?period_id={period_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _period_id(client: TestClient, h: dict[str, str], mes: int) -> str:
    periods = client.get("/api/v1/periods", headers=h).json()
    return next(p["id"] for p in periods if p["mes"] == mes)


def test_pool_available_after_deposit(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    h, period_id, _ = _setup_meta_pool(client, token)
    goal_id = _create_goal(client, h)

    before = _pool_summary(client, h, period_id)
    assert Decimal(before["pool_total"]) == Decimal("500")
    assert Decimal(before["available"]) == Decimal("500")

    dep = client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={"tipo": "deposit", "valor": "100", "data": "2026-01-20"},
        headers=h,
    )
    assert dep.status_code == 201, dep.text

    after = _pool_summary(client, h, period_id)
    assert Decimal(after["deposited_total"]) == Decimal("100")
    assert Decimal(after["available"]) == Decimal("400")


def test_pool_available_after_withdraw_without_income(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    h, period_id, _ = _setup_meta_pool(client, token)
    goal_id = _create_goal(client, h)

    client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={"tipo": "deposit", "valor": "100", "data": "2026-01-20"},
        headers=h,
    )
    wd = client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={"tipo": "withdraw", "valor": "100", "data": "2026-01-21"},
        headers=h,
    )
    assert wd.status_code == 201, wd.text

    summary = _pool_summary(client, h, period_id)
    assert Decimal(summary["deposited_total"]) == Decimal("0")
    assert Decimal(summary["available"]) == Decimal("500")


def test_pool_available_after_withdraw_as_income(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    h, period_id, income_cat_id = _setup_meta_pool(client, token)
    goal_id = _create_goal(client, h)

    client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={"tipo": "deposit", "valor": "100", "data": "2026-01-20"},
        headers=h,
    )
    wd = client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={
            "tipo": "withdraw",
            "valor": "100",
            "data": "2026-01-21",
            "launch_as_income": True,
            "categoria_id": income_cat_id,
        },
        headers=h,
    )
    assert wd.status_code == 201, wd.text

    summary = _pool_summary(client, h, period_id)
    assert Decimal(summary["deposited_total"]) == Decimal("0")
    assert Decimal(summary["available"]) == Decimal("400")


def test_pool_available_unchanged_after_deleting_empty_goal(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    h, period_id, income_cat_id = _setup_meta_pool(client, token)
    goal_id = _create_goal(client, h)

    client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={"tipo": "deposit", "valor": "100", "data": "2026-01-20"},
        headers=h,
    )
    client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={
            "tipo": "withdraw",
            "valor": "100",
            "data": "2026-01-21",
            "launch_as_income": True,
            "categoria_id": income_cat_id,
        },
        headers=h,
    )

    before_delete = _pool_summary(client, h, period_id)
    assert Decimal(before_delete["available"]) == Decimal("400")

    deleted = client.delete(f"/api/v1/goals/{goal_id}", headers=h)
    assert deleted.status_code == 204, deleted.text

    after_delete = _pool_summary(client, h, period_id)
    assert Decimal(after_delete["available"]) == Decimal(before_delete["available"])
    assert Decimal(after_delete["deposited_total"]) == Decimal("0")


def test_pool_available_increases_when_deleting_goal_with_balance(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    h, period_id, _ = _setup_meta_pool(client, token)
    goal_id = _create_goal(client, h)

    client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={"tipo": "deposit", "valor": "150", "data": "2026-01-20"},
        headers=h,
    )

    before_delete = _pool_summary(client, h, period_id)
    assert Decimal(before_delete["available"]) == Decimal("350")
    assert Decimal(before_delete["deposited_total"]) == Decimal("150")

    deleted = client.delete(f"/api/v1/goals/{goal_id}", headers=h)
    assert deleted.status_code == 204, deleted.text

    after_delete = _pool_summary(client, h, period_id)
    assert Decimal(after_delete["available"]) == Decimal("500")
    assert Decimal(after_delete["deposited_total"]) == Decimal("0")


def test_pool_available_zero_after_deleting_withdraw_incomes_and_meta_expenses(client: TestClient) -> None:
    """Cenário do usuário: apagar receitas de retirada e despesas Metas não deve deixar disponível negativo."""
    _, _, token = register_and_token(client)
    h, period_id, income_cat_id = _setup_meta_pool(client, token, pool_amount="500.00")
    goal_id = _create_goal(client, h)

    client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={"tipo": "deposit", "valor": "500", "data": "2026-01-20"},
        headers=h,
    )
    wd = client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={
            "tipo": "withdraw",
            "valor": "500",
            "data": "2026-01-21",
            "launch_as_income": True,
            "categoria_id": income_cat_id,
        },
        headers=h,
    )
    assert wd.status_code == 201, wd.text

    before = _pool_summary(client, h, period_id)
    assert Decimal(before["available"]) == Decimal("0")

    incomes = client.get(f"/api/v1/incomes?period_id={period_id}", headers=h).json()
    for inc in incomes:
        if inc["descricao"].startswith("Retirada:"):
            deleted = client.delete(f"/api/v1/incomes/{inc['id']}", headers=h)
            assert deleted.status_code == 204, deleted.text

    expenses = client.get(f"/api/v1/expenses?period_id={period_id}", headers=h).json()
    for exp in expenses:
        if exp["tipo"] == "fixed":
            deleted = client.delete(f"/api/v1/expenses/{exp['id']}", headers=h)
            assert deleted.status_code == 204, deleted.text

    after = _pool_summary(client, h, period_id)
    assert Decimal(after["pool_total"]) == Decimal("0")
    assert Decimal(after["available"]) == Decimal("0")


def test_pool_available_restored_when_deleting_withdraw_income_only(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    h, period_id, income_cat_id = _setup_meta_pool(client, token)
    goal_id = _create_goal(client, h)

    client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={"tipo": "deposit", "valor": "100", "data": "2026-01-20"},
        headers=h,
    )
    client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={
            "tipo": "withdraw",
            "valor": "100",
            "data": "2026-01-21",
            "launch_as_income": True,
            "categoria_id": income_cat_id,
        },
        headers=h,
    )

    assert Decimal(_pool_summary(client, h, period_id)["available"]) == Decimal("400")

    incomes = client.get(f"/api/v1/incomes?period_id={period_id}", headers=h).json()
    withdraw_income = next(i for i in incomes if i["descricao"].startswith("Retirada:"))
    deleted = client.delete(f"/api/v1/incomes/{withdraw_income['id']}", headers=h)
    assert deleted.status_code == 204, deleted.text

    after = _pool_summary(client, h, period_id)
    assert Decimal(after["pool_total"]) == Decimal("500")
    assert Decimal(after["available"]) == Decimal("500")


def test_pool_available_zero_after_deleting_meta_expenses_and_persisted_withdraw(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    h, period_id, income_cat_id = _setup_meta_pool(client, token)
    goal_id = _create_goal(client, h)

    client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={"tipo": "deposit", "valor": "100", "data": "2026-01-20"},
        headers=h,
    )
    client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={
            "tipo": "withdraw",
            "valor": "100",
            "data": "2026-01-21",
            "launch_as_income": True,
            "categoria_id": income_cat_id,
        },
        headers=h,
    )
    assert client.delete(f"/api/v1/goals/{goal_id}", headers=h).status_code == 204

    expenses = client.get(f"/api/v1/expenses?period_id={period_id}", headers=h).json()
    for exp in expenses:
        if exp["tipo"] == "fixed":
            assert client.delete(f"/api/v1/expenses/{exp['id']}", headers=h).status_code == 204

    after = _pool_summary(client, h, period_id)
    assert Decimal(after["pool_total"]) == Decimal("0")
    assert Decimal(after["available"]) == Decimal("0")


def test_pool_is_isolated_per_month(client: TestClient) -> None:
    """Dinheiro separado em setembro não pode aparecer como disponível em agosto."""
    _, _, token = register_and_token(client)
    h, _, _ = _setup_meta_pool(client, token)
    agosto = _period_id(client, h, 8)
    setembro = _period_id(client, h, 9)

    meta_cat_id = next(
        c["id"] for c in client.get("/api/v1/categories?tipo=expense", headers=h).json()
        if c["nome"] == "Metas reserva"
    )
    exp = client.post(
        "/api/v1/expenses",
        json={
            "descricao": "Reserva metas setembro",
            "valor": "700.00",
            "data": "2026-09-05",
            "period_id": setembro,
            "categoria_id": meta_cat_id,
            "tipo": "fixed",
            "pago": True,
        },
        headers=h,
    )
    assert exp.status_code == 201, exp.text

    em_agosto = _pool_summary(client, h, agosto)
    assert Decimal(em_agosto["pool_total"]) == Decimal("0")
    assert Decimal(em_agosto["available"]) == Decimal("0")

    em_setembro = _pool_summary(client, h, setembro)
    assert Decimal(em_setembro["pool_total"]) == Decimal("700")
    assert Decimal(em_setembro["available"]) == Decimal("700")


def test_deposit_consumes_only_its_own_month(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    h, janeiro, _ = _setup_meta_pool(client, token)
    fevereiro = _period_id(client, h, 2)
    goal_id = _create_goal(client, h)

    dep = client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={"tipo": "deposit", "valor": "200", "data": "2026-01-20"},
        headers=h,
    )
    assert dep.status_code == 201, dep.text

    assert Decimal(_pool_summary(client, h, janeiro)["available"]) == Decimal("300")
    assert Decimal(_pool_summary(client, h, fevereiro)["available"]) == Decimal("0")

    sem_pool = client.post(
        f"/api/v1/goals/{goal_id}/transactions",
        json={"tipo": "deposit", "valor": "50", "data": "2026-02-10"},
        headers=h,
    )
    assert sem_pool.status_code == 400, sem_pool.text
