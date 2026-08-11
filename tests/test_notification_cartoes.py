from datetime import date

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_token, setup_year_and_category


def _current_period_id(client: TestClient, headers: dict[str, str]) -> str:
    """Mesma escolha de NotificationService._current_period: o período do mês corrente."""
    today = date.today()
    periods = client.get("/api/v1/periods", headers=headers).json()
    match = next(
        (p for p in periods if p["ano"] == today.year and p["mes"] == today.month),
        None,
    )
    assert match is not None, f"No period for {today.year}-{today.month}"
    return match["id"]


def _latest_open_period_id(client: TestClient, headers: dict[str, str]) -> str:
    periods = client.get("/api/v1/periods", headers=headers).json()
    open_ones = [p for p in periods if p["status"] == "open"]
    assert open_ones, "No open periods"
    open_ones.sort(key=lambda p: (p["ano"], p["mes"]), reverse=True)
    return open_ones[0]["id"]


def _create_card(client: TestClient, headers: dict[str, str], nome: str, banco: str) -> str:
    today = date.today()
    resp = client.post(
        "/api/v1/cards",
        json={
            "nome": nome,
            "banco": banco,
            "limite": "5000.00",
            "fechamento": 1 if today.day != 1 else 15,
            "vencimento": today.day,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_tx(
    client: TestClient,
    headers: dict[str, str],
    *,
    card_id: str,
    cat_id: str,
    period_id: str,
    valor: str,
) -> str:
    resp = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Compra",
            "valor": valor,
            "data": date.today().isoformat(),
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": period_id,
            "pago": False,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()[0]["id"]


def _generate(client: TestClient, headers: dict[str, str], *, force: bool = False) -> None:
    url = "/api/v1/notifications/gerar" + ("?force=true" if force else "")
    resp = client.post(url, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["ran"] is True


def _card_notifications(client: TestClient, headers: dict[str, str]) -> list[dict]:
    resp = client.get("/api/v1/notifications", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["grupos"]["cartoes"]


def test_fatura_vencendo_skips_when_unpaid_zero(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    setup_year_and_category(client, token, ano=date.today().year)
    h = auth_headers(token)
    _create_card(client, h, "Azul", "Itau")

    _generate(client, h)

    tipos = {n["tipo"] for n in _card_notifications(client, h)}
    assert "fatura_vencendo_urgente" not in tipos
    assert "fatura_vencendo_atencao" not in tipos
    assert "fatura_fechou" not in tipos


def test_fatura_vencendo_uses_current_month_value(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    _, cat_id = setup_year_and_category(client, token, ano=date.today().year)
    h = auth_headers(token)
    card_id = _create_card(client, h, "Santander", "Santander")
    _create_tx(
        client,
        h,
        card_id=card_id,
        cat_id=cat_id,
        period_id=_current_period_id(client, h),
        valor="120.50",
    )

    _generate(client, h)

    urgentes = [n for n in _card_notifications(client, h) if n["tipo"] == "fatura_vencendo_urgente"]
    assert len(urgentes) == 1
    assert urgentes[0]["titulo"] == "Fatura vence hoje"
    assert "R$ 120,50 pendente" in urgentes[0]["subtitulo"]


def test_valor_do_ultimo_periodo_aberto_nao_e_usado(client: TestClient) -> None:
    """Lançamento em dezembro não deve virar valor da fatura de hoje."""
    today = date.today()
    if today.month == 12:
        return
    _, _, token = register_and_token(client)
    _, cat_id = setup_year_and_category(client, token, ano=today.year)
    h = auth_headers(token)
    card_id = _create_card(client, h, "Azul", "Itau")
    _create_tx(
        client,
        h,
        card_id=card_id,
        cat_id=cat_id,
        period_id=_latest_open_period_id(client, h),
        valor="999.00",
    )

    _generate(client, h)

    tipos = {n["tipo"] for n in _card_notifications(client, h)}
    assert "fatura_vencendo_urgente" not in tipos


def test_notificacao_obsoleta_e_removida_ao_pagar(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    _, cat_id = setup_year_and_category(client, token, ano=date.today().year)
    h = auth_headers(token)
    card_id = _create_card(client, h, "Santander", "Santander")
    tx_id = _create_tx(
        client,
        h,
        card_id=card_id,
        cat_id=cat_id,
        period_id=_current_period_id(client, h),
        valor="80.00",
    )

    _generate(client, h)
    assert any(n["tipo"] == "fatura_vencendo_urgente" for n in _card_notifications(client, h))

    paid = client.post(f"/api/v1/card-transactions/{tx_id}/paid?pago=true", headers=h)
    assert paid.status_code == 200, paid.text

    _generate(client, h, force=True)

    tipos = {n["tipo"] for n in _card_notifications(client, h)}
    assert "fatura_vencendo_urgente" not in tipos


def test_valor_alterado_atualiza_notificacao_existente(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    _, cat_id = setup_year_and_category(client, token, ano=date.today().year)
    h = auth_headers(token)
    period_id = _current_period_id(client, h)
    card_id = _create_card(client, h, "Santander", "Santander")
    _create_tx(client, h, card_id=card_id, cat_id=cat_id, period_id=period_id, valor="80.00")

    _generate(client, h)
    antes = [n for n in _card_notifications(client, h) if n["tipo"] == "fatura_vencendo_urgente"]
    assert len(antes) == 1
    assert "R$ 80,00 pendente" in antes[0]["subtitulo"]

    _create_tx(client, h, card_id=card_id, cat_id=cat_id, period_id=period_id, valor="20.00")
    _generate(client, h, force=True)

    depois = [n for n in _card_notifications(client, h) if n["tipo"] == "fatura_vencendo_urgente"]
    assert len(depois) == 1
    assert depois[0]["id"] == antes[0]["id"]
    assert "R$ 100,00 pendente" in depois[0]["subtitulo"]


def test_criado_em_inclui_fuso(client: TestClient) -> None:
    _, _, token = register_and_token(client)
    _, cat_id = setup_year_and_category(client, token, ano=date.today().year)
    h = auth_headers(token)
    card_id = _create_card(client, h, "Santander", "Santander")
    _create_tx(
        client,
        h,
        card_id=card_id,
        cat_id=cat_id,
        period_id=_current_period_id(client, h),
        valor="50.00",
    )

    _generate(client, h)

    cartoes = _card_notifications(client, h)
    assert cartoes
    criado_em = cartoes[0]["criado_em"]
    assert criado_em.endswith("Z") or "+" in criado_em[10:]
