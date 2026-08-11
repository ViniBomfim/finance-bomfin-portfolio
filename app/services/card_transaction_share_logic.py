from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status

from app.repositories.spender_repository import SpenderRepository
from app.schemas.card_schema import CardTransactionShareInput

SHARE_SUM_TOLERANCE = Decimal("0.02")

SharePair = tuple[UUID, Decimal]
ShareTriple = tuple[UUID, Decimal, bool]


def normalize_share_template(
    user_id: UUID,
    spender_repo: SpenderRepository,
    inputs: list[CardTransactionShareInput] | None,
    must_sum_to: Decimal,
    *,
    existing_pago_by_spender: dict[UUID, bool] | None = None,
) -> list[ShareTriple]:
    if not inputs:
        return []
    pairs: list[ShareTriple] = []
    for row in inputs:
        sp = spender_repo.get_by_id(row.spender_id, user_id)
        if sp is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pessoa (spender) não encontrada",
            )
        pago = row.pago
        if existing_pago_by_spender is not None and "pago" not in row.model_fields_set:
            pago = existing_pago_by_spender.get(row.spender_id, False)
        pairs.append((row.spender_id, row.valor, pago))
    total = sum((v for _, v, _ in pairs), Decimal("0"))
    if abs(total - must_sum_to) > SHARE_SUM_TOLERANCE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A soma das partes ({total}) deve ser igual ao valor do lançamento ({must_sum_to}).",
        )
    return pairs


def scale_shares_to_line(
    template: list[SharePair] | list[ShareTriple],
    line_val: Decimal,
    purchase_total: Decimal,
) -> list[SharePair]:
    """Propaga proporções do template (que somam purchase_total) para uma linha com valor line_val."""
    if not template:
        return []
    if purchase_total == 0:
        return []
    amount_template: list[SharePair] = [
        (row[0], row[1]) for row in template
    ]
    if len(amount_template) == 1:
        return [(amount_template[0][0], line_val.quantize(Decimal("0.01")))]
    out: list[SharePair] = []
    acc = Decimal("0")
    n = len(amount_template)
    for i, (sid, v) in enumerate(amount_template):
        if i == n - 1:
            part = (line_val - acc).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            part = (v / purchase_total * line_val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            acc += part
        out.append((sid, part))
    drift = line_val - sum(p for _, p in out)
    if abs(drift) >= Decimal("0.005") and out:
        sid, last = out[-1]
        out[-1] = (sid, (last + drift).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return out


def attach_pago(
    scaled: list[SharePair],
    pago_by_spender: dict[UUID, bool],
    *,
    default_pago: bool = False,
) -> list[ShareTriple]:
    return [(sid, val, pago_by_spender.get(sid, default_pago)) for sid, val in scaled]
