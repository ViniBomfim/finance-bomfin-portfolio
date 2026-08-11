"""Junta totais por categoria vindos de despesas e de transações de cartão."""

from decimal import Decimal
from uuid import UUID


def merge_expense_and_card_category_rows(
    expense_rows: list[tuple[UUID, str, float]],
    card_rows: list[tuple[UUID, str, float]],
) -> list[tuple[UUID, str, Decimal]]:
    merged: dict[UUID, tuple[str, Decimal]] = {}
    for cid, nome, amt in expense_rows:
        merged[cid] = (nome, Decimal(str(amt)))
    for cid, nome, amt in card_rows:
        d = Decimal(str(amt))
        if cid in merged:
            n, prev = merged[cid]
            merged[cid] = (n, prev + d)
        else:
            merged[cid] = (nome, d)
    return [(cid, nome, tot) for cid, (nome, tot) in merged.items()]
