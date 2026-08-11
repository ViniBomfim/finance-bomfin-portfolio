from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.card_transaction import CardTransaction
from app.models.card_transaction_share import CardTransactionShare
from app.services.dashboard_cache import DashboardCache


class CardTransactionShareRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_transaction(self, card_transaction_id: UUID) -> list[CardTransactionShare]:
        stmt = (
            select(CardTransactionShare)
            .options(selectinload(CardTransactionShare.spender))
            .where(CardTransactionShare.card_transaction_id == card_transaction_id)
            .order_by(CardTransactionShare.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def delete_for_transaction(self, card_transaction_id: UUID, *, commit: bool = True) -> None:
        stmt = delete(CardTransactionShare).where(
            CardTransactionShare.card_transaction_id == card_transaction_id
        )
        self.db.execute(stmt)
        if commit:
            tx = self.db.get(CardTransaction, card_transaction_id)
            self.db.commit()
            if tx is not None:
                DashboardCache.invalidate_user_period(tx.user_id, tx.period_id)
        else:
            self.db.flush()

    def delete_for_transactions(self, card_transaction_ids: list[UUID], *, commit: bool = True) -> None:
        if not card_transaction_ids:
            return
        stmt = delete(CardTransactionShare).where(
            CardTransactionShare.card_transaction_id.in_(card_transaction_ids)
        )
        self.db.execute(stmt)
        if commit:
            self.db.commit()
        else:
            self.db.flush()

    def create_many(
        self, rows: list[CardTransactionShare], *, commit: bool = True
    ) -> list[CardTransactionShare]:
        if not rows:
            return rows
        tx_by_id: dict[UUID, CardTransaction] = {}
        for row in rows:
            if row.card_transaction_id not in tx_by_id:
                tx = self.db.get(CardTransaction, row.card_transaction_id)
                if tx is not None:
                    tx_by_id[row.card_transaction_id] = tx
        for r in rows:
            self.db.add(r)
        if commit:
            self.db.commit()
            for r in rows:
                self.db.refresh(r)
            for tx in tx_by_id.values():
                DashboardCache.invalidate_user_period(tx.user_id, tx.period_id)
        else:
            self.db.flush()
        return rows

    def list_transactions_with_shares_for_card_period(
        self, user_id: UUID, card_id: UUID, period_id: UUID
    ) -> list[CardTransaction]:
        stmt = (
            select(CardTransaction)
            .options(
                selectinload(CardTransaction.categoria),
                selectinload(CardTransaction.shares).selectinload(CardTransactionShare.spender),
            )
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.card_id == card_id,
                CardTransaction.period_id == period_id,
            )
            .order_by(CardTransaction.data.asc(), CardTransaction.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_transactions_with_shares_for_period(
        self,
        user_id: UUID,
        period_id: UUID,
    ) -> list[CardTransaction]:
        stmt = (
            select(CardTransaction)
            .options(
                selectinload(CardTransaction.categoria),
                selectinload(CardTransaction.shares).selectinload(CardTransactionShare.spender),
            )
            .where(
                CardTransaction.user_id == user_id,
                CardTransaction.period_id == period_id,
            )
            .order_by(CardTransaction.data.asc(), CardTransaction.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_transactions_with_shares_for_user(self, user_id: UUID) -> list[CardTransaction]:
        stmt = (
            select(CardTransaction)
            .options(
                selectinload(CardTransaction.categoria),
                selectinload(CardTransaction.shares).selectinload(CardTransactionShare.spender),
            )
            .where(CardTransaction.user_id == user_id)
            .order_by(CardTransaction.data.asc(), CardTransaction.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())
