"""Testes HTTP de preview e parsers PDF por texto."""

from io import BytesIO

from app.services.statement_parse_service import parse_nubank_pdf_text, parse_pdf_br_lines
from tests.conftest import auth_headers, register_and_token, setup_year_and_category


def test_parse_nubank_pdf_text_extracts_purchase_and_skips_summary() -> None:
    text = "\n".join(
        [
            "10 JUL Pedagio*DEMO001 R$ 3,65",
            "10 JUL Valor pendente do mês anterior R$ 1.250,00",
            "11 JUL Pagamento recebido - R$ 1.250,00",
            "18 JUL Parque Demo*Atracao R$ 312,00",
        ]
    )
    rows = parse_nubank_pdf_text(text, "2026-07-10")
    descs = [r.descricao.lower() for r in rows]
    assert any("pedagio" in d for d in descs)
    assert any("parque demo" in d for d in descs)
    assert not any("pendente" in d for d in descs)
    assert not any("pagamento" in d for d in descs)


def test_parse_pdf_br_lines_keeps_purchase() -> None:
    text = "15/07/2026 SUPERMERCADO XYZ R$ 41,02"
    rows = parse_pdf_br_lines(text, "2026-07-15")
    assert len(rows) >= 1
    assert any("supermercado" in r.descricao.lower() for r in rows)


def test_preview_endpoint_nubank_csv_roundtrip(client) -> None:
    _, _, token = register_and_token(client)
    h = auth_headers(token)
    period_id, _cat_id = setup_year_and_category(client, token, ano=2026)

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

    csv_body = "\n".join(
        [
            "date,title,amount",
            '2026-07-11,Pagamento recebido,"- 100,00"',
            '2026-07-10,Valor pendente do mês anterior,"100,00"',
            '2026-07-10,Pedagio*DEMO001,"3,65"',
            '2026-07-10,Uber - NuPay,"19,94"',
        ]
    ).encode("utf-8")

    resp = client.post(
        "/api/v1/statement-import/preview",
        headers=h,
        data={
            "format_id": "nubank_csv",
            "default_date": "2026-07-10",
            "card_id": card_id,
            "period_id": period_id,
        },
        files={"file": ("nubank.csv", BytesIO(csv_body), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["format_used"] == "nubank_csv"
    assert body["summary"]["new"] >= 2
    statuses = {(r["descricao"], r["status"], r.get("skip_reason")) for r in body["rows"]}
    assert any(d.startswith("Pedagio") and st == "new" for d, st, _ in statuses)
    assert any(d.startswith("Uber") and st == "new" for d, st, _ in statuses)
    # Linhas de pagamento/resumo: ou filtradas no parse (não aparecem) ou skip no preview.
    assert not any("pendente" in d.lower() and st == "new" for d, st, _ in statuses)
    assert not any("pagamento" in d.lower() and st == "new" for d, st, _ in statuses)
