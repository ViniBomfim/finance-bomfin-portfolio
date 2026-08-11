"""Junção de linhas de várias heurísticas de PDF — evita duplicar o mesmo lançamento."""

from app.services.statement_parse_service import (
    _Row,
    _concat_rows_merge_parsers,
    _is_purchase_description,
    extract_parcela_from_description,
)


def test_merge_keeps_distinct_installments() -> None:
    a = _Row(data="2026-04-01", descricao="Loja - Parcela 2/10", valor="10.00")
    b = _Row(data="2026-04-01", descricao="Loja - Parcela 3/10", valor="10.00")
    out = _concat_rows_merge_parsers([a], [b])
    assert len(out) == 2


def test_merge_drops_duplicate_from_two_parsers() -> None:
    x = _Row(data="2026-04-01", descricao="Mercado X", valor="5.00")
    out = _concat_rows_merge_parsers([x], [x])
    assert len(out) == 1


def test_merge_keeps_repeated_same_purchase_inside_single_parser() -> None:
    """Mesmo dia/descrição/valor pode acontecer mais de uma vez na fatura (ex.: pedágio)."""
    x = _Row(data="2026-04-01", descricao="Transação de Pedagio", valor="18.50")
    out = _concat_rows_merge_parsers([x, x], [])
    assert len(out) == 2


def test_merge_keeps_max_repeated_occurrence_across_parsers() -> None:
    """Se dois parsers capturam o mesmo lançamento, mantém a quantidade real (não soma duplicado técnico)."""
    x = _Row(data="2026-04-01", descricao="Transação de Pedagio", valor="18.50")
    out = _concat_rows_merge_parsers([x, x], [x])
    assert len(out) == 2


def test_merge_keeps_plain_and_parcel_as_separate_when_different_keys() -> None:
    """Não colapsamos mais resumo + detalhe — evita apagar compra à vista legítima."""
    plain = _Row(data="2026-04-01", descricao="Casasbahiacom", valor="217.65")
    with_parcel = _Row(
        data="2026-04-01",
        descricao="Casasbahiacom - Parcela 8/9",
        valor="217.65",
    )
    out = _concat_rows_merge_parsers([plain], [with_parcel])
    assert len(out) == 2


def test_merge_slightly_different_text_same_purchase_one_row() -> None:
    a = _Row(data="2026-04-10", descricao="Pedagio *Loja", valor="42.00")
    b = _Row(data="2026-04-10", descricao="Pedagio *Loja ", valor="42.00")
    out = _concat_rows_merge_parsers([a], [b])
    assert len(out) == 1


def test_merge_two_cash_purchases_same_merchant_same_value_kept() -> None:
    """À vista: descrições completas diferentes não colapsam."""
    a = _Row(data="2026-04-05", descricao="Padaria item A", valor="15.00")
    b = _Row(data="2026-04-05", descricao="Padaria item B", valor="15.00")
    out = _concat_rows_merge_parsers([a], [b])
    assert len(out) == 2


def test_purchase_filter_skips_pagamento_efetuado() -> None:
    assert _is_purchase_description("PAGAMENTO EFETUADO") is False


def test_extract_parcela_from_plain_suffix_fraction() -> None:
    desc, pa, pt = extract_parcela_from_description("Loja XPTO 2/10")
    assert desc == "Loja XPTO"
    assert pa == 2
    assert pt == 10


def test_extract_parcela_from_plain_suffix_with_word() -> None:
    desc, pa, pt = extract_parcela_from_description("Loja XPTO parcela 3/12")
    assert desc == "Loja XPTO"
    assert pa == 3
    assert pt == 12
