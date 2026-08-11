"""Testes de classificação de importação de fatura."""

from decimal import Decimal
from uuid import uuid4

from app.models.card_transaction import CardTransaction
from app.schemas.statement_import_schema import ParsedStatementRow
from app.services.statement_import_preview_service import classify_statement_rows


def _tx(
    data: str,
    desc: str,
    valor: str,
    inum: int = 1,
    itotal: int = 1,
    cat_id=None,
    *,
    from_statement: bool = False,
) -> CardTransaction:
    tx = CardTransaction(
        id=uuid4(),
        descricao=desc,
        valor=Decimal(valor),
        data=__import__("datetime").date.fromisoformat(data),
        pago=False,
        from_statement=from_statement,
        installment_number=inum,
        installment_total=itotal,
        card_id=uuid4(),
        categoria_id=cat_id,
        period_id=uuid4(),
        user_id=uuid4(),
    )
    return tx


def test_exact_match_is_kept():
    existing = [_tx("2026-06-15", "Conta Vivo", "77.03")]
    rows = [
        ParsedStatementRow(data="2026-06-15", descricao="Conta Vivo", valor="77.03"),
    ]
    out = classify_statement_rows(rows, existing)
    assert len(out) == 1
    assert out[0].status == "kept"


def test_new_row_when_not_in_db():
    rows = [
        ParsedStatementRow(data="2026-06-26", descricao="Mcdonalds", valor="38.90"),
    ]
    out = classify_statement_rows(rows, [])
    assert len(out) == 1
    assert out[0].status == "new"


def test_updated_when_desc_differs_same_value():
    existing = [_tx("2026-06-15", "UBER TRIP*AID781", "39.97")]
    rows = [
        ParsedStatementRow(
            data="2026-06-15",
            descricao="Uber Uber *Trip Help.U",
            valor="39.97",
        ),
    ]
    out = classify_statement_rows(rows, existing)
    assert len(out) == 1
    assert out[0].status == "updated"
    assert out[0].update_kind == "descricao"


def test_updated_when_valor_differs_similar_desc():
    existing = [_tx("2026-06-08", "Mercadodxltda", "594.45")]
    rows = [
        ParsedStatementRow(
            data="2026-06-08",
            descricao="Mercadodxltda",
            valor="612.30",
        ),
    ]
    out = classify_statement_rows(rows, existing)
    assert len(out) == 1
    assert out[0].status == "updated"
    assert out[0].update_kind == "valor"


def test_payment_line_is_skip():
    rows = [
        ParsedStatementRow(data="2026-06-01", descricao="Pagamento recebido", valor="-100.00"),
    ]
    out = classify_statement_rows(rows, [])
    assert len(out) == 1
    assert out[0].status == "skip"
    assert out[0].skip_reason == "payment_line"


def test_valor_pendente_is_skip_summary():
    rows = [
        ParsedStatementRow(
            data="2026-07-10",
            descricao="Valor pendente do mês anterior",
            valor="1250.00",
        ),
    ]
    out = classify_statement_rows(rows, [])
    assert len(out) == 1
    assert out[0].status == "skip"
    assert out[0].skip_reason == "summary_line"


def test_installment_match_updated_when_valor_and_date_differ():
    """Parcela 2/3 já gerada pelo PDF com valor/data errados vs CSV da fatura."""
    existing = [_tx("2026-05-18", "Cea Tte 107 Ecpc", "120.00", inum=2, itotal=3)]
    rows = [
        ParsedStatementRow(
            data="2026-06-03",
            descricao="Cea Tte 107 Ecpc",
            valor="119.99",
            parcela_atual=2,
            parcela_total=3,
        ),
    ]
    out = classify_statement_rows(rows, existing)
    assert len(out) == 1
    assert out[0].status == "updated"
    assert out[0].update_kind == "valor"
    assert out[0].previous_valor == "120.00"
    assert out[0].previous_data == "2026-05-18"


def test_installment_match_kept_when_valor_data_and_desc_match():
    existing = [_tx("2026-06-03", "Cea Tte 107 Ecpc", "119.99", inum=2, itotal=3)]
    rows = [
        ParsedStatementRow(
            data="2026-06-03",
            descricao="Cea Tte 107 Ecpc",
            valor="119.99",
            parcela_atual=2,
            parcela_total=3,
        ),
    ]
    out = classify_statement_rows(rows, existing)
    assert len(out) == 1
    assert out[0].status == "kept"


def test_same_purchase_different_date_is_new_not_updated():
    """Mesma desc+valor em data diferente = compra distinta (ex.: pedágio), não atualização."""
    existing = [_tx("2026-07-17", "Parque Demo*Atracao", "312.00")]
    rows = [
        ParsedStatementRow(
            data="2026-07-18",
            descricao="Parque Demo*Atracao",
            valor="312.00",
        ),
    ]
    out = classify_statement_rows(rows, existing)
    assert len(out) == 1
    assert out[0].status == "new"
    assert out[0].existing_transaction_id is None


def test_pedagio_same_value_different_dates_stay_kept():
    """Repetições legítimas (pedágio) em dias distintos não colapsam um no outro."""
    existing = [
        _tx("2026-07-03", "Pedagio*DEMO001", "3.65"),
        _tx("2026-07-09", "Pedagio*DEMO001", "3.65"),
    ]
    rows = [
        ParsedStatementRow(data="2026-07-03", descricao="Pedagio*DEMO001", valor="3.65"),
        ParsedStatementRow(data="2026-07-09", descricao="Pedagio*DEMO001", valor="3.65"),
    ]
    out = classify_statement_rows(rows, existing)
    assert len(out) == 2
    assert out[0].status == "kept"
    assert out[1].status == "kept"
    assert {out[0].existing_transaction_id, out[1].existing_transaction_id} == {
        existing[0].id,
        existing[1].id,
    }


def test_pedagio_new_date_is_new_not_update_of_previous():
    """Novo pedágio em outra data não atualiza o lançamento antigo do mesmo valor."""
    existing = [_tx("2026-07-21", "Pedagio*DEMO001", "3.00")]
    rows = [
        ParsedStatementRow(data="2026-07-27", descricao="Pedagio*DEMO001", valor="3.00"),
    ]
    out = classify_statement_rows(rows, existing)
    assert len(out) == 1
    assert out[0].status == "new"


def test_same_desc_value_different_date_among_many_is_new():
    existing = [
        _tx("2026-07-10", "Loja X", "50.00"),
        _tx("2026-07-17", "Loja X", "50.00"),
    ]
    rows = [
        ParsedStatementRow(data="2026-07-18", descricao="Loja X", valor="50.00"),
    ]
    out = classify_statement_rows(rows, existing)
    assert len(out) == 1
    assert out[0].status == "new"


def test_import_confirm_date_mismatch_creates_instead_of_updating(client):
    """Confirm com create na mesma desc+valor e data diferente cria novo lançamento."""
    from tests.conftest import auth_headers, register_and_token, setup_year_and_category

    _, _, token = register_and_token(client)
    h = auth_headers(token)
    period_id, cat_id = setup_year_and_category(client, token, ano=2026)

    card = client.post(
        "/api/v1/cards",
        json={
            "nome": "Ultravioleta",
            "banco": "Nubank",
            "limite": "10000.00",
            "fechamento": 10,
            "vencimento": 17,
        },
        headers=h,
    )
    assert card.status_code == 201, card.text
    card_id = card.json()["id"]

    created = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Pedagio*DEMO001",
            "valor": "3.00",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": period_id,
            "data": "2026-07-21",
            "pago": False,
            "from_statement": True,
        },
        headers=h,
    )
    assert created.status_code == 201, created.text
    tx_id = created.json()[0]["id"]

    confirm = client.post(
        "/api/v1/statement-import/confirm",
        json={
            "card_id": card_id,
            "period_id": period_id,
            "creates": [
                {
                    "data": "2026-07-27",
                    "descricao": "Pedagio*DEMO001",
                    "valor": "3.00",
                    "categoria_id": cat_id,
                }
            ],
            "updates": [],
        },
        headers=h,
    )
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()
    assert body["created"] == 1
    assert body["updated"] == 0

    listed = client.get(
        f"/api/v1/card-transactions?card_id={card_id}&period_id={period_id}",
        headers=h,
    )
    assert listed.status_code == 200, listed.text
    txs = [t for t in listed.json() if "Pedagio" in t["descricao"]]
    assert len(txs) == 2
    dates = {t["data"] for t in txs}
    assert dates == {"2026-07-21", "2026-07-27"}
    assert any(t["id"] == tx_id for t in txs)


def test_import_confirm_rescales_shares_when_valor_updates(client):
    """Atualizar valor na importação reescala divisão existente em vez de retornar 400."""
    from tests.conftest import auth_headers, register_and_token, setup_year_and_category

    _, _, token = register_and_token(client)
    h = auth_headers(token)
    period_id, cat_id = setup_year_and_category(client, token, ano=2026)

    card = client.post(
        "/api/v1/cards",
        json={
            "nome": "Ultravioleta",
            "banco": "Nubank",
            "limite": "10000.00",
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
    spender_a, spender_b = s_a.json()["id"], s_b.json()["id"]

    created = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Restaurante Split",
            "valor": "100.00",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": period_id,
            "data": "2026-08-05",
            "pago": False,
            "from_statement": True,
            "shares": [
                {"spender_id": spender_a, "valor": "60.00"},
                {"spender_id": spender_b, "valor": "40.00"},
            ],
        },
        headers=h,
    )
    assert created.status_code == 201, created.text
    tx_id = created.json()[0]["id"]

    confirm = client.post(
        "/api/v1/statement-import/confirm",
        json={
            "card_id": card_id,
            "period_id": period_id,
            "creates": [],
            "updates": [
                {
                    "transaction_id": tx_id,
                    "apply": True,
                    "valor": "110.00",
                }
            ],
        },
        headers=h,
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["updated"] == 1

    listed = client.get(
        f"/api/v1/card-transactions?card_id={card_id}&period_id={period_id}",
        headers=h,
    )
    assert listed.status_code == 200, listed.text
    tx = next(t for t in listed.json() if t["id"] == tx_id)
    assert Decimal(str(tx["valor"])) == Decimal("110.00")
    shares = tx.get("shares") or []
    assert len(shares) == 2
    by_spender = {sh["spender_id"]: Decimal(str(sh["valor"])) for sh in shares}
    assert by_spender[spender_a] == Decimal("66.00")
    assert by_spender[spender_b] == Decimal("44.00")
    assert sum(by_spender.values()) == Decimal("110.00")


def test_import_confirm_diverted_create_rescales_shares(client):
    """Create que casa parcela X/Y existente e muda valor também reescala shares."""
    from tests.conftest import auth_headers, register_and_token, setup_year_and_category

    _, _, token = register_and_token(client)
    h = auth_headers(token)
    period_id, cat_id = setup_year_and_category(client, token, ano=2026)

    card = client.post(
        "/api/v1/cards",
        json={
            "nome": "Ultravioleta",
            "banco": "Nubank",
            "limite": "10000.00",
            "fechamento": 10,
            "vencimento": 17,
        },
        headers=h,
    )
    assert card.status_code == 201, card.text
    card_id = card.json()["id"]

    s_a = client.post("/api/v1/spenders", json={"nome": "Ana"}, headers=h)
    s_b = client.post("/api/v1/spenders", json={"nome": "Bruno"}, headers=h)
    assert s_a.status_code == 201 and s_b.status_code == 201
    spender_a, spender_b = s_a.json()["id"], s_b.json()["id"]

    created = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Loja Parcela",
            "valor": "100.00",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": period_id,
            "data": "2026-08-01",
            "pago": False,
            "from_statement": True,
            "installment_number": 2,
            "installment_total": 3,
            "shares": [
                {"spender_id": spender_a, "valor": "60.00"},
                {"spender_id": spender_b, "valor": "40.00"},
            ],
        },
        headers=h,
    )
    assert created.status_code == 201, created.text
    tx_id = created.json()[0]["id"]

    confirm = client.post(
        "/api/v1/statement-import/confirm",
        json={
            "card_id": card_id,
            "period_id": period_id,
            "creates": [
                {
                    "data": "2026-08-05",
                    "descricao": "Loja Parcela - Parcela 2/3",
                    "valor": "110.00",
                    "parcela_atual": 2,
                    "parcela_total": 3,
                    "categoria_id": cat_id,
                }
            ],
            "updates": [],
        },
        headers=h,
    )
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()
    assert body["created"] == 0
    assert body["updated"] == 1

    listed = client.get(
        f"/api/v1/card-transactions?card_id={card_id}&period_id={period_id}",
        headers=h,
    )
    assert listed.status_code == 200, listed.text
    tx = next(t for t in listed.json() if t["id"] == tx_id)
    assert Decimal(str(tx["valor"])) == Decimal("110.00")
    shares = tx.get("shares") or []
    by_spender = {sh["spender_id"]: Decimal(str(sh["valor"])) for sh in shares}
    assert by_spender[spender_a] == Decimal("66.00")
    assert by_spender[spender_b] == Decimal("44.00")


def test_glued_itau_parcela_only_bad_row_matches_as_kept():
    """Descrição colada NORTEA06/10 (1/1) casa com linha correta 6/10 do arquivo."""
    existing = [
        _tx("2026-02-21", "SUMUP*LOJA NORTEA06/10", "200.00", from_statement=True),
    ]
    rows = [
        ParsedStatementRow(
            data="2026-02-21",
            descricao="SUMUP*LOJA NORTEA",
            valor="200.00",
            parcela_atual=6,
            parcela_total=10,
        ),
    ]
    out = classify_statement_rows(rows, existing)
    statuses = [r.status for r in out]
    assert "kept" in statuses or "updated" in statuses
    assert "orphan" not in statuses
    matched = next(r for r in out if r.status in ("kept", "updated"))
    assert matched.existing_transaction_id == existing[0].id


def test_glued_next_invoice_and_correct_current_yields_orphan():
    """Com linha correta 6/10 e residual colado 07/10, o residual vira órfão."""
    bad = _tx("2026-02-21", "SUMUP*LOJA NORTEA07/10", "200.00", from_statement=True)
    good = _tx(
        "2026-02-21",
        "SUMUP*LOJA NORTEA",
        "200.00",
        inum=6,
        itotal=10,
        from_statement=True,
    )
    rows = [
        ParsedStatementRow(
            data="2026-02-21",
            descricao="SUMUP*LOJA NORTEA",
            valor="200.00",
            parcela_atual=6,
            parcela_total=10,
        ),
    ]
    out = classify_statement_rows(rows, [bad, good])
    by_status = {}
    for r in out:
        by_status.setdefault(r.status, []).append(r)
    assert len(by_status.get("kept", [])) + len(by_status.get("updated", [])) == 1
    orphans = by_status.get("orphan", [])
    assert len(orphans) == 1
    assert orphans[0].existing_transaction_id == bad.id
    assert orphans[0].remove_by_default is True


def test_manual_tx_is_not_reported_as_orphan():
    existing = [_tx("2026-07-01", "Compra manual", "50.00", from_statement=False)]
    rows = [
        ParsedStatementRow(data="2026-07-10", descricao="Outra loja", valor="10.00"),
    ]
    out = classify_statement_rows(rows, existing)
    assert all(r.status != "orphan" for r in out)
    assert any(r.status == "new" for r in out)


def test_next_invoice_installment_becomes_orphan():
    existing = [
        _tx("2026-07-16", "SAMSUMMER -CT", "154.98", inum=1, itotal=2, from_statement=True),
        _tx("2026-07-16", "SAMSUMMER -CT", "154.98", inum=2, itotal=2, from_statement=True),
    ]
    rows = [
        ParsedStatementRow(
            data="2026-07-16",
            descricao="SAMSUMMER -CT",
            valor="154.98",
            parcela_atual=1,
            parcela_total=2,
        ),
    ]
    out = classify_statement_rows(rows, existing)
    orphans = [r for r in out if r.status == "orphan"]
    assert len(orphans) == 1
    assert orphans[0].parcela_atual == 2


def test_import_confirm_deletes_from_statement_orphans(client):
    from tests.conftest import auth_headers, register_and_token, setup_year_and_category

    _, _, token = register_and_token(client)
    h = auth_headers(token)
    period_id, cat_id = setup_year_and_category(client, token, ano=2026)

    card = client.post(
        "/api/v1/cards",
        json={
            "nome": "Itaú PDA",
            "banco": "Itaú",
            "limite": "10000.00",
            "fechamento": 30,
            "vencimento": 6,
        },
        headers=h,
    )
    assert card.status_code == 201, card.text
    card_id = card.json()["id"]

    keep = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "ACADEMIA PASS",
            "valor": "139.90",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": period_id,
            "data": "2026-07-28",
            "pago": False,
            "from_statement": True,
        },
        headers=h,
    )
    assert keep.status_code == 201, keep.text

    orphan = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "SUMUP*LOJA NORTEA07/10",
            "valor": "200.00",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": period_id,
            "data": "2026-02-21",
            "pago": False,
            "from_statement": True,
        },
        headers=h,
    )
    assert orphan.status_code == 201, orphan.text
    orphan_id = orphan.json()[0]["id"]

    confirm = client.post(
        "/api/v1/statement-import/confirm",
        json={
            "card_id": card_id,
            "period_id": period_id,
            "creates": [],
            "updates": [],
            "deletes": [orphan_id],
        },
        headers=h,
    )
    assert confirm.status_code == 200, confirm.text
    body = confirm.json()
    assert body["deleted"] == 1
    assert "removido" in body["message"].lower()

    listed = client.get(
        f"/api/v1/card-transactions?card_id={card_id}&period_id={period_id}",
        headers=h,
    )
    assert listed.status_code == 200, listed.text
    ids = {t["id"] for t in listed.json()}
    assert orphan_id not in ids
    assert any(t["descricao"] == "ACADEMIA PASS" for t in listed.json())


def test_import_confirm_rejects_delete_of_manual_tx(client):
    from tests.conftest import auth_headers, register_and_token, setup_year_and_category

    _, _, token = register_and_token(client)
    h = auth_headers(token)
    period_id, cat_id = setup_year_and_category(client, token, ano=2026)

    card = client.post(
        "/api/v1/cards",
        json={
            "nome": "Itaú Azul",
            "banco": "Itaú",
            "limite": "5000.00",
            "fechamento": 10,
            "vencimento": 17,
        },
        headers=h,
    )
    assert card.status_code == 201, card.text
    card_id = card.json()["id"]

    manual = client.post(
        "/api/v1/card-transactions",
        json={
            "descricao": "Lançamento manual",
            "valor": "50.00",
            "card_id": card_id,
            "categoria_id": cat_id,
            "period_id": period_id,
            "data": "2026-07-15",
            "pago": False,
            "from_statement": False,
        },
        headers=h,
    )
    assert manual.status_code == 201, manual.text
    manual_id = manual.json()[0]["id"]

    confirm = client.post(
        "/api/v1/statement-import/confirm",
        json={
            "card_id": card_id,
            "period_id": period_id,
            "creates": [],
            "updates": [],
            "deletes": [manual_id],
        },
        headers=h,
    )
    assert confirm.status_code == 400, confirm.text
