from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUserId
from app.database.connection import get_db
from app.models.trip_expense import TripExpense
from app.trips.schemas import (
    PushToMonthRequest,
    TripCreate,
    TripExpenseCreate,
    TripExpenseResponse,
    TripExpenseShareResponse,
    TripExpenseUpdate,
    TripParticipantInput,
    TripResponse,
    TripSettlementResponse,
    TripUpdate,
)
from app.trips.service import TripService

router = APIRouter(prefix="/trips", tags=["trips"])


def _trip_expense_response(expense: TripExpense) -> TripExpenseResponse:
    shares = [
        TripExpenseShareResponse(
            spender_id=sh.spender_id,
            spender_nome=sh.spender.nome if sh.spender else "",
            valor=sh.valor,
        )
        for sh in (expense.shares or [])
    ]
    return TripExpenseResponse(
        id=expense.id,
        trip_id=expense.trip_id,
        user_id=expense.user_id,
        descricao=expense.descricao,
        valor=expense.valor,
        moeda=expense.moeda,
        taxa_cambio=expense.taxa_cambio,
        valor_base=expense.valor_base,
        data=expense.data,
        categoria=expense.categoria,
        forma_pagamento=expense.forma_pagamento,
        paid_by_spender_id=expense.paid_by_spender_id,
        paid_by_nome=expense.paid_by.nome if expense.paid_by else "",
        observacao=expense.observacao,
        pushed_expense_id=expense.pushed_expense_id,
        shares=shares,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
    )


@router.get("", response_model=list[TripResponse])
def list_trips(user_id: CurrentUserId, db: Session = Depends(get_db)) -> list[TripResponse]:
    rows = TripService(db).list_trips(user_id)
    return [TripResponse.model_validate(x) for x in rows]


@router.post("", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
def create_trip(
    data: TripCreate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> TripResponse:
    row = TripService(db).create_trip(user_id, data)
    return TripResponse.model_validate(row)


@router.get("/{trip_id}", response_model=TripResponse)
def get_trip(
    trip_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> TripResponse:
    row = TripService(db).get_trip(user_id, trip_id)
    return TripResponse.model_validate(row)


@router.patch("/{trip_id}", response_model=TripResponse)
def update_trip(
    trip_id: UUID,
    data: TripUpdate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> TripResponse:
    row = TripService(db).update_trip(user_id, trip_id, data)
    return TripResponse.model_validate(row)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(
    trip_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> None:
    TripService(db).delete_trip(user_id, trip_id)


@router.post(
    "/{trip_id}/participants",
    response_model=TripResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_participant(
    trip_id: UUID,
    data: TripParticipantInput,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> TripResponse:
    row = TripService(db).add_participant(user_id, trip_id, data)
    return TripResponse.model_validate(row)


@router.delete(
    "/{trip_id}/participants/{spender_id}",
    response_model=TripResponse,
)
def remove_participant(
    trip_id: UUID,
    spender_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> TripResponse:
    row = TripService(db).remove_participant(user_id, trip_id, spender_id)
    return TripResponse.model_validate(row)


@router.get("/{trip_id}/expenses", response_model=list[TripExpenseResponse])
def list_trip_expenses(
    trip_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> list[TripExpenseResponse]:
    rows = TripService(db).list_expenses(user_id, trip_id)
    return [_trip_expense_response(x) for x in rows]


@router.post(
    "/{trip_id}/expenses",
    response_model=TripExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_trip_expense(
    trip_id: UUID,
    data: TripExpenseCreate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> TripExpenseResponse:
    row = TripService(db).create_expense(user_id, trip_id, data)
    return _trip_expense_response(row)


@router.patch("/expenses/{expense_id}", response_model=TripExpenseResponse)
def update_trip_expense(
    expense_id: UUID,
    data: TripExpenseUpdate,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> TripExpenseResponse:
    row = TripService(db).update_expense(user_id, expense_id, data)
    return _trip_expense_response(row)


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip_expense(
    expense_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> None:
    TripService(db).delete_expense(user_id, expense_id)


@router.post("/expenses/{expense_id}/push-to-month", response_model=TripExpenseResponse)
def push_to_month(
    expense_id: UUID,
    body: PushToMonthRequest,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> TripExpenseResponse:
    row = TripService(db).push_to_month(user_id, expense_id, body)
    return _trip_expense_response(row)


@router.get("/{trip_id}/settlement", response_model=TripSettlementResponse)
def get_trip_settlement(
    trip_id: UUID,
    user_id: CurrentUserId,
    db: Session = Depends(get_db),
) -> TripSettlementResponse:
    return TripService(db).settlement(user_id, trip_id)
