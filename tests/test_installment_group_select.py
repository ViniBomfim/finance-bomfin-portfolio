"""Seleção de parcelas da mesma compra ao apagar período (cartão)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.repositories.card_transaction_repository import select_installment_group_members


def _row(desc: str, d: date, valor: str, num: int, total: int = 10) -> SimpleNamespace:
    return SimpleNamespace(
        descricao=desc,
        data=d,
        valor=Decimal(valor),
        installment_number=num,
        installment_total=total,
    )


def test_same_norm_and_valor_groups_despite_different_data() -> None:
    """Fatura: mesma loja e valor por parcela; data pode variar entre meses no extrato."""
    d1, d2 = date(2026, 4, 5), date(2026, 5, 1)
    rows = [
        _row("Loja ABC", d1, "50.00", 4),
        _row("Loja ABC - Parcela 5/10", d2, "50.00", 5),
    ]
    out = select_installment_group_members(
        rows, descricao=rows[0].descricao, data_iso=rows[0].data, valor=rows[0].valor
    )
    assert len(out) == 2
    assert {x.installment_number for x in out} == {4, 5}


def test_manual_split_same_data_different_valor_per_line() -> None:
    """Parcelamento manual: mesma data, valores arredondados diferentes por mês."""
    d0 = date(2026, 3, 10)
    rows = [
        _row("Curso", d0, "33.33", 1, total=3),
        _row("Curso", d0, "33.33", 2, total=3),
        _row("Curso", d0, "33.34", 3, total=3),
    ]
    out = select_installment_group_members(
        rows, descricao=rows[0].descricao, data_iso=rows[0].data, valor=rows[0].valor
    )
    assert len(out) == 3


def test_legacy_exact_desc_and_data_still_works() -> None:
    d = date(2026, 1, 1)
    rows = [
        _row("X", d, "10.00", 1, total=2),
        _row("X", d, "10.00", 2, total=2),
    ]
    out = select_installment_group_members(rows, descricao="X", data_iso=d, valor=Decimal("10.00"))
    assert len(out) == 2
