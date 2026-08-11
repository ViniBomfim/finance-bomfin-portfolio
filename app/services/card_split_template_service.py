from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.card_split_template import CardSplitTemplate
from app.repositories.card_split_template_repository import CardSplitTemplateRepository
from app.services.card_transaction_share_logic import SHARE_SUM_TOLERANCE, scale_shares_to_line


class CardSplitTemplateService:
    """Persiste e reaplica proporções de divisão por (cartão + descrição canônica)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CardSplitTemplateRepository(db)

    def save_from_pairs(
        self,
        user_id: UUID,
        card_id: UUID,
        description_key: str,
        pairs: list[tuple[UUID, Decimal]],
        total_valor: Decimal,
        *,
        commit: bool = True,
    ) -> None:
        if not pairs or total_valor <= 0:
            self.repo.delete_by_key(user_id, card_id, description_key)
            return
        s = sum((v for _, v in pairs), Decimal("0"))
        if abs(s - total_valor) > SHARE_SUM_TOLERANCE:
            return
        ratios: list[tuple[UUID, Decimal]] = []
        for sid, v in pairs:
            ratios.append((sid, (v / total_valor).quantize(Decimal("0.0000000001"))))
        drift = Decimal("1") - sum(r for _, r in ratios)
        if ratios and abs(drift) > Decimal("0.0000001"):
            sid, last = ratios[-1]
            ratios[-1] = (sid, (last + drift).quantize(Decimal("0.0000000001")))
        parts = [{"spender_id": str(sid), "ratio": str(r)} for sid, r in ratios]
        self.repo.upsert(
            CardSplitTemplate(
                user_id=user_id,
                card_id=card_id,
                description_key=description_key[:500],
                parts=parts,
            ),
            commit=commit,
        )

    def pairs_for_valor(
        self, user_id: UUID, card_id: UUID, description_key: str, line_valor: Decimal
    ) -> list[tuple[UUID, Decimal]] | None:
        if line_valor <= 0:
            return None
        row = self.repo.get_by_key(user_id, card_id, description_key[:500])
        if row is None or not row.parts:
            return None
        try:
            ratio_pairs: list[tuple[UUID, Decimal]] = []
            for p in row.parts:
                ratio_pairs.append((UUID(p["spender_id"]), Decimal(p["ratio"])))
        except (KeyError, ValueError, TypeError):
            return None
        if not ratio_pairs:
            return None
        rsum = sum(r for _, r in ratio_pairs)
        if abs(rsum - Decimal("1")) > Decimal("0.02"):
            return None
        tpl = [(sid, r) for sid, r in ratio_pairs]
        return scale_shares_to_line(tpl, line_valor, Decimal("1"))

    def delete_for_key(self, user_id: UUID, card_id: UUID, description_key: str) -> None:
        self.repo.delete_by_key(user_id, card_id, description_key[:500])
