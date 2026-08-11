"""Parsers CSV dedicados por banco (cartão)."""

from app.services.statement_parse_service import (
    extract_parcela_from_description,
    parse_generic_csv,
    parse_itau_azul_csv,
    parse_itau_pda_csv,
    parse_santander_csv,
)


def test_parse_itau_azul_csv_reads_fraction_installment_column() -> None:
    text = "\n".join(
        [
            "Data;Estabelecimento;Parcela;Valor",
            "24/04/2026;LOJA AZUL;6/6;185,06",
        ]
    )
    rows = parse_itau_azul_csv(text, "2026-04-24")
    assert len(rows) == 1
    desc, pa, pt = extract_parcela_from_description(rows[0].descricao)
    assert desc == "LOJA AZUL"
    assert (pa, pt) == (6, 6)


def test_parse_santander_csv_reads_parcela_de_text() -> None:
    text = "\n".join(
        [
            "Data;Descrição;Parcela;Valor",
            "24/04/2026;LOJA SANTANDER;12 de 12;39,95",
        ]
    )
    rows = parse_santander_csv(text, "2026-04-24")
    assert len(rows) == 1
    desc, pa, pt = extract_parcela_from_description(rows[0].descricao)
    assert desc == "LOJA SANTANDER"
    assert (pa, pt) == (12, 12)


def test_parse_itau_pda_csv_reads_current_and_total_columns() -> None:
    text = "\n".join(
        [
            "Data;Descrição;Parcela Atual;Total de Parcelas;Valor",
            "24/04/2026;LOJA PDA;2;10;100,00",
        ]
    )
    rows = parse_itau_pda_csv(text, "2026-04-24")
    assert len(rows) == 1
    desc, pa, pt = extract_parcela_from_description(rows[0].descricao)
    assert desc == "LOJA PDA"
    assert (pa, pt) == (2, 10)


def test_parse_itau_azul_csv_reads_installment_from_extra_text_column() -> None:
    text = "\n".join(
        [
            "Data;Estabelecimento;Detalhe;Valor",
            "24/04/2026;LOJA EXTRA;Parcela 6 de 6;185,06",
        ]
    )
    rows = parse_itau_azul_csv(text, "2026-04-24")
    assert len(rows) == 1
    desc, pa, pt = extract_parcela_from_description(rows[0].descricao)
    assert desc == "LOJA EXTRA"
    assert (pa, pt) == (6, 6)


def test_parse_itau_azul_csv_reads_money_when_value_has_extra_text() -> None:
    text = "\n".join(
        [
            "Data;Estabelecimento;Valor",
            "24/04/2026;LOJA VALOR;185,06 parcela 6 de 6",
        ]
    )
    rows = parse_itau_azul_csv(text, "2026-04-24")
    assert len(rows) == 1
    desc, pa, pt = extract_parcela_from_description(rows[0].descricao)
    assert desc == "LOJA VALOR"
    assert (pa, pt) == (6, 6)


def test_parse_itau_azul_csv_reads_installment_with_ordinal_symbol() -> None:
    text = "\n".join(
        [
            "Data;Estabelecimento;Detalhe;Valor",
            "24/04/2026;LOJA ORDINARIA;6ª parcela de 6;185,06",
        ]
    )
    rows = parse_itau_azul_csv(text, "2026-04-24")
    assert len(rows) == 1
    desc, pa, pt = extract_parcela_from_description(rows[0].descricao)
    assert desc == "LOJA ORDINARIA"
    assert (pa, pt) == (6, 6)


def test_parse_generic_csv_skips_pagamento_com_saldo() -> None:
    text = "\n".join(
        [
            "Data;Descrição;Valor",
            "08/04/2026;PAGAMENTO COM SALDO;-1009,11",
            "15/04/2026;Compra normal;40,50",
        ]
    )
    rows = parse_generic_csv(text, "2026-04-24")
    assert len(rows) == 1
    assert rows[0].descricao == "Compra normal"


def test_parse_nubank_csv_skips_valor_pendente_and_pagamento() -> None:
    from app.services.statement_parse_service import parse_nubank_csv

    text = "\n".join(
        [
            "date,title,amount",
            '2026-07-11,Pagamento recebido,"- 1.250,00"',
            '2026-07-10,Valor pendente do mês anterior,"1.250,00"',
            '2026-07-10,Pedagio*DEMO001,"3,65"',
            '2026-07-10,Saldo anterior,"100,00"',
        ]
    )
    rows = parse_nubank_csv(text, "2026-07-10")
    assert len(rows) == 1
    assert rows[0].descricao == "Pedagio*DEMO001"
    assert rows[0].valor == "3.65"
