from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.schemas.card_schema import (
    CardCreate,
    CardResponse,
    CardTransactionsBulkDeleteAllMonthsResponse,
    CardTransactionsBulkDeleteResponse,
    CardTransactionsMarkPaidResponse,
    CardUpdate,
)
from app.schemas.card_spender_summary_schema import CardSpenderSummaryResponse
from app.services.card_service import CardService
from app.services.card_transaction_service import CardTransactionService

router = APIRouter(prefix="/cards", tags=["cards"])


@router.post("", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
def create_card(data: CardCreate, user_id: CurrentUserId, db: Session = Depends(get_db)) -> CardResponse:
    c = CardService(db).create(user_id, data)
    return CardResponse.model_validate(c)


@router.get("", response_model=list[CardResponse])
def list_cards(user_id: CurrentUserId, db: Session = Depends(get_db)) -> list[CardResponse]:
    rows = CardService(db).list_cards(user_id)
    return [CardResponse.model_validate(x) for x in rows]


@router.delete(
    "/{card_id}/transactions",
    response_model=CardTransactionsBulkDeleteResponse,
    status_code=status.HTTP_200_OK,
)
def delete_all_card_transactions(
    card_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    period_id: UUID = Query(..., description="Período: apaga somente lançamentos deste mês no cartão (parcelas em outros meses permanecem)"),
) -> CardTransactionsBulkDeleteResponse:
    n = CardTransactionService(db).delete_period_and_linked_installments(user_id, card_id, period_id)
    return CardTransactionsBulkDeleteResponse(card_id=card_id, period_id=period_id, deleted=n)


@router.delete(
    "/{card_id}/transactions/all-months",
    response_model=CardTransactionsBulkDeleteAllMonthsResponse,
    status_code=status.HTTP_200_OK,
)
def delete_all_card_transactions_all_months(
    card_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> CardTransactionsBulkDeleteAllMonthsResponse:
    n = CardTransactionService(db).delete_all_transactions_in_all_card_periods(user_id, card_id)
    return CardTransactionsBulkDeleteAllMonthsResponse(card_id=card_id, deleted=n)


@router.post(
    "/{card_id}/transactions/mark-paid",
    response_model=CardTransactionsMarkPaidResponse,
    status_code=status.HTTP_200_OK,
)
def mark_all_card_transactions_paid(
    card_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    period_id: UUID = Query(..., description="Período: marca todos os lançamentos como pagos"),
) -> CardTransactionsMarkPaidResponse:
    n = CardTransactionService(db).mark_all_paid_in_period(user_id, card_id, period_id)
    return CardTransactionsMarkPaidResponse(card_id=card_id, period_id=period_id, updated=n)


@router.get("/{card_id}/spender-summary", response_model=CardSpenderSummaryResponse)
def card_spender_summary(
    card_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
    period_id: UUID = Query(...),
) -> CardSpenderSummaryResponse:
    return CardTransactionService(db).spenders_summary(user_id, card_id, period_id)


@router.get("/{card_id}", response_model=CardResponse)
def get_card(card_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> CardResponse:
    c = CardService(db).get(user_id, card_id)
    return CardResponse.model_validate(c)


@router.patch("/{card_id}", response_model=CardResponse)
def update_card(
    card_id: UUID,
    data: CardUpdate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> CardResponse:
    c = CardService(db).update(user_id, card_id, data)
    return CardResponse.model_validate(c)


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(card_id: UUID, user_id: CurrentUserId, db: Session = Depends(get_db)) -> None:
    CardService(db).delete(user_id, card_id)
