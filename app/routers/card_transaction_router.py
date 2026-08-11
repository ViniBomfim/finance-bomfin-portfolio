from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.models.card_transaction import CardTransaction
from app.schemas.card_schema import (
    CardSpentTotalResponse,
    CardTransactionCreate,
    CardTransactionResponse,
    CardTransactionShareResponse,
    CardTransactionUpdate,
    InvoiceTotalResponse,
)
from app.services.card_transaction_service import CardTransactionService

router = APIRouter(prefix="/card-transactions", tags=["card-transactions"])


def _tx_response(tx: CardTransaction) -> CardTransactionResponse:
    sh: list[CardTransactionShareResponse] = []
    if tx.shares:
        for s in tx.shares:
            sh.append(
                CardTransactionShareResponse(
                    spender_id=s.spender_id,
                    spender_nome=s.spender.nome if s.spender else "",
                    valor=s.valor,
                    pago=bool(getattr(s, "pago", False)),
                )
            )
    return CardTransactionResponse(
        id=tx.id,
        descricao=tx.descricao,
        valor=tx.valor,
        data=tx.data,
        pago=tx.pago,
        from_statement=tx.from_statement,
        installment_number=tx.installment_number,
        installment_total=tx.installment_total,
        installment_group_id=tx.installment_group_id,
        card_id=tx.card_id,
        categoria_id=tx.categoria_id,
        categoria_nome=tx.categoria.nome if tx.categoria else None,
        period_id=tx.period_id,
        user_id=tx.user_id,
        created_at=tx.created_at,
        updated_at=tx.updated_at,
        shares=sh,
    )


@router.post("", response_model=list[CardTransactionResponse], status_code=status.HTTP_201_CREATED)
def create_transaction(
    data: CardTransactionCreate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> list[CardTransactionResponse]:
    rows = CardTransactionService(db).create(user_id, data)
    return [_tx_response(x) for x in rows]


@router.get("/invoice-total", response_model=InvoiceTotalResponse)
def invoice_total(
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    card_id: UUID = Query(...),
    period_id: UUID = Query(...),
) -> InvoiceTotalResponse:
    svc = CardTransactionService(db)
    total, unpaid_total, unpaid_count, paid_at = svc.invoice_total(user_id, card_id, period_id)
    return InvoiceTotalResponse(
        card_id=card_id,
        period_id=period_id,
        total=total,
        unpaid_total=unpaid_total,
        unpaid_count=unpaid_count,
        paid_at=paid_at,
    )


@router.get("/spent-total", response_model=CardSpentTotalResponse)
def spent_total(
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    card_id: UUID = Query(...),
) -> CardSpentTotalResponse:
    svc = CardTransactionService(db)
    total = svc.total_spent_on_card(user_id, card_id)
    return CardSpentTotalResponse(card_id=card_id, total=total)


@router.get("", response_model=list[CardTransactionResponse])
def list_transactions(
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    card_id: UUID = Query(...),
    period_id: UUID = Query(...),
) -> list[CardTransactionResponse]:
    rows = CardTransactionService(db).list_card_expenses(user_id, card_id, period_id)
    return [_tx_response(x) for x in rows]


@router.get("/{tx_id}", response_model=CardTransactionResponse)
def get_transaction(tx_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> CardTransactionResponse:
    tx = CardTransactionService(db).get(user_id, tx_id)
    return _tx_response(tx)


@router.patch("/{tx_id}", response_model=CardTransactionResponse)
def update_transaction(
    tx_id: UUID,
    data: CardTransactionUpdate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> CardTransactionResponse:
    tx = CardTransactionService(db).update(user_id, tx_id, data)
    return _tx_response(tx)


@router.post("/{tx_id}/shares/{spender_id}/paid", response_model=CardTransactionResponse)
def mark_share_paid(
    tx_id: UUID,
    spender_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    pago: bool = Query(True, description="true = pago, false = pendente"),
) -> CardTransactionResponse:
    tx = CardTransactionService(db).set_share_paid(user_id, tx_id, spender_id, pago=pago)
    return _tx_response(tx)


@router.post("/{tx_id}/paid", response_model=CardTransactionResponse)
def mark_transaction_paid(
    tx_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    pago: bool = Query(True, description="true = pago, false = pendente"),
) -> CardTransactionResponse:
    tx = CardTransactionService(db).set_all_shares_paid(user_id, tx_id, pago)
    return _tx_response(tx)


@router.delete("/{tx_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(tx_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> None:
    CardTransactionService(db).delete(user_id, tx_id)
