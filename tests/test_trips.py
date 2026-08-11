from decimal import Decimal

from tests.conftest import auth_headers, register_and_token, setup_year_and_category


def _to_decimal(value: str | float | int) -> Decimal:
    return Decimal(str(value))


def _create_spender(client, headers, nome: str) -> str:
    r = client.post("/api/v1/spenders", headers=headers, json={"nome": nome})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_trip(client, headers, *, participant_ids: list[str]) -> dict:
    r = client.post(
        "/api/v1/trips",
        headers=headers,
        json={
            "nome": "Viagem teste",
            "destino": "Salvador",
            "data_inicio": "2026-06-01",
            "data_fim": "2026-06-07",
            "moeda_base": "BRL",
            "orcamento_total": "5000.00",
            "participant_spender_ids": participant_ids,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_trip_create_and_lists_participants(client):
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    s_a = _create_spender(client, h, "Ana")
    s_b = _create_spender(client, h, "Bruno")

    trip = _create_trip(client, h, participant_ids=[s_a, s_b])
    assert trip["nome"] == "Viagem teste"
    assert trip["status"] == "planning"
    assert _to_decimal(trip["total_gasto"]) == Decimal("0.00")
    assert {p["spender_id"] for p in trip["participants"]} == {s_a, s_b}

    listing = client.get("/api/v1/trips", headers=h)
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_trip_expense_auto_split_and_settlement(client):
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    s_a = _create_spender(client, h, "Ana")
    s_b = _create_spender(client, h, "Bruno")
    s_c = _create_spender(client, h, "Carla")
    trip = _create_trip(client, h, participant_ids=[s_a, s_b, s_c])

    # Ana paga R$ 300 jantar — divide automaticamente em 3 (100/100/100)
    e1 = client.post(
        f"/api/v1/trips/{trip['id']}/expenses",
        headers=h,
        json={
            "descricao": "Jantar",
            "valor": "300.00",
            "data": "2026-06-02",
            "categoria": "meal",
            "paid_by_spender_id": s_a,
        },
    )
    assert e1.status_code == 201, e1.text
    body1 = e1.json()
    assert len(body1["shares"]) == 3
    assert sum(_to_decimal(sh["valor"]) for sh in body1["shares"]) == Decimal("300.00")

    # Bruno paga R$ 90 hotel só dele e da Carla
    e2 = client.post(
        f"/api/v1/trips/{trip['id']}/expenses",
        headers=h,
        json={
            "descricao": "Café da manhã",
            "valor": "90.00",
            "data": "2026-06-03",
            "categoria": "hotel",
            "paid_by_spender_id": s_b,
            "shares": [
                {"spender_id": s_b, "valor": "45.00"},
                {"spender_id": s_c, "valor": "45.00"},
            ],
        },
    )
    assert e2.status_code == 201, e2.text

    # Settlement
    s = client.get(f"/api/v1/trips/{trip['id']}/settlement", headers=h)
    assert s.status_code == 200, s.text
    body = s.json()
    saldos = {row["spender_id"]: _to_decimal(row["saldo"]) for row in body["saldos"]}
    # Ana pagou 300 e consumiu 100  -> saldo +200
    assert saldos[s_a] == Decimal("200.00")
    # Bruno pagou 90 e consumiu 100 + 45 = 145 -> saldo -55
    assert saldos[s_b] == Decimal("-55.00")
    # Carla pagou 0 e consumiu 100 + 45 = 145 -> saldo -145
    assert saldos[s_c] == Decimal("-145.00")

    # Transferências mínimas: Carla -> Ana (145), Bruno -> Ana (55)
    transfers = body["transferencias"]
    total = sum(_to_decimal(t["valor"]) for t in transfers)
    assert total == Decimal("200.00")
    by_pair = {(t["from_spender_id"], t["to_spender_id"]): _to_decimal(t["valor"]) for t in transfers}
    assert by_pair[(s_c, s_a)] == Decimal("145.00")
    assert by_pair[(s_b, s_a)] == Decimal("55.00")


def test_trip_share_must_match_total(client):
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    s_a = _create_spender(client, h, "Ana")
    s_b = _create_spender(client, h, "Bruno")
    trip = _create_trip(client, h, participant_ids=[s_a, s_b])

    bad = client.post(
        f"/api/v1/trips/{trip['id']}/expenses",
        headers=h,
        json={
            "descricao": "Algo",
            "valor": "100.00",
            "data": "2026-06-02",
            "categoria": "other",
            "paid_by_spender_id": s_a,
            "shares": [
                {"spender_id": s_a, "valor": "60.00"},
                {"spender_id": s_b, "valor": "30.00"},
            ],
        },
    )
    assert bad.status_code == 400
    assert "soma" in bad.json()["detail"].lower()


def test_trip_paid_by_must_be_participant(client):
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    s_a = _create_spender(client, h, "Ana")
    s_b = _create_spender(client, h, "Bruno")
    s_outsider = _create_spender(client, h, "Outsider")
    trip = _create_trip(client, h, participant_ids=[s_a, s_b])

    r = client.post(
        f"/api/v1/trips/{trip['id']}/expenses",
        headers=h,
        json={
            "descricao": "Algo",
            "valor": "50.00",
            "data": "2026-06-02",
            "categoria": "other",
            "paid_by_spender_id": s_outsider,
        },
    )
    assert r.status_code == 400
    assert "participante" in r.json()["detail"].lower()


def test_trip_push_to_month_creates_expense(client):
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    period_id, _ = setup_year_and_category(client, token)
    s_a = _create_spender(client, h, "Ana")
    s_b = _create_spender(client, h, "Bruno")
    trip = _create_trip(client, h, participant_ids=[s_a, s_b])

    e = client.post(
        f"/api/v1/trips/{trip['id']}/expenses",
        headers=h,
        json={
            "descricao": "Hotel",
            "valor": "200.00",
            "data": "2026-06-02",
            "categoria": "hotel",
            "paid_by_spender_id": s_a,
        },
    )
    assert e.status_code == 201, e.text
    expense_id = e.json()["id"]

    pushed = client.post(
        f"/api/v1/trips/expenses/{expense_id}/push-to-month",
        headers=h,
        json={"period_id": period_id, "pago": True},
    )
    assert pushed.status_code == 200, pushed.text
    assert pushed.json()["pushed_expense_id"] is not None

    # Tentar empurrar de novo deve falhar
    again = client.post(
        f"/api/v1/trips/expenses/{expense_id}/push-to-month",
        headers=h,
        json={"period_id": period_id},
    )
    assert again.status_code == 400

    # A despesa deve ter sido criada na lista mensal
    monthly = client.get(f"/api/v1/expenses?period_id={period_id}", headers=h)
    assert monthly.status_code == 200
    descricoes = [exp["descricao"] for exp in monthly.json()]
    assert "Hotel" in descricoes


def test_trip_closed_blocks_mutations(client):
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    s_a = _create_spender(client, h, "Ana")
    s_b = _create_spender(client, h, "Bruno")
    trip = _create_trip(client, h, participant_ids=[s_a, s_b])

    # encerrar
    closed = client.patch(
        f"/api/v1/trips/{trip['id']}",
        headers=h,
        json={"status": "closed"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"

    # adicionar gasto deve falhar
    blocked = client.post(
        f"/api/v1/trips/{trip['id']}/expenses",
        headers=h,
        json={
            "descricao": "Não",
            "valor": "10.00",
            "data": "2026-06-02",
            "categoria": "other",
            "paid_by_spender_id": s_a,
        },
    )
    assert blocked.status_code == 400
    assert "encerr" in blocked.json()["detail"].lower()


def test_trip_isolated_per_user(client):
    _, _, token_a = register_and_token(client)
    h_a = auth_headers(token_a)
    _, _, token_b = register_and_token(client)
    h_b = auth_headers(token_b)

    s_a = _create_spender(client, h_a, "Ana")
    trip_a = _create_trip(client, h_a, participant_ids=[s_a])

    # outro usuário não vê
    r = client.get(f"/api/v1/trips/{trip_a['id']}", headers=h_b)
    assert r.status_code == 404
