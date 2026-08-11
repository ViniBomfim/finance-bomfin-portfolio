from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.trip import Trip
from app.models.trip_expense import TripExpense
from app.models.trip_expense_share import TripExpenseShare
from app.models.trip_participant import TripParticipant


class TripRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_user(self, user_id: UUID) -> list[Trip]:
        stmt = (
            select(Trip)
            .options(
                selectinload(Trip.participants).selectinload(TripParticipant.spender),
                selectinload(Trip.expenses).selectinload(TripExpense.shares),
            )
            .where(Trip.user_id == user_id)
            .order_by(Trip.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id(self, trip_id: UUID, user_id: UUID) -> Trip | None:
        stmt = (
            select(Trip)
            .options(
                selectinload(Trip.participants).selectinload(TripParticipant.spender),
            )
            .where(Trip.id == trip_id, Trip.user_id == user_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_with_expenses(self, trip_id: UUID, user_id: UUID) -> Trip | None:
        stmt = (
            select(Trip)
            .options(
                selectinload(Trip.participants).selectinload(TripParticipant.spender),
                selectinload(Trip.expenses)
                .selectinload(TripExpense.shares)
                .selectinload(TripExpenseShare.spender),
                selectinload(Trip.expenses).selectinload(TripExpense.paid_by),
            )
            .where(Trip.id == trip_id, Trip.user_id == user_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, trip: Trip) -> Trip:
        self.db.add(trip)
        self.db.commit()
        self.db.refresh(trip)
        return trip

    def update(self, trip: Trip) -> Trip:
        self.db.commit()
        self.db.refresh(trip)
        return trip

    def delete(self, trip: Trip) -> None:
        self.db.delete(trip)
        self.db.commit()


class TripParticipantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_trip(self, trip_id: UUID) -> list[TripParticipant]:
        stmt = (
            select(TripParticipant)
            .options(selectinload(TripParticipant.spender))
            .where(TripParticipant.trip_id == trip_id)
            .order_by(TripParticipant.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get(self, trip_id: UUID, spender_id: UUID) -> TripParticipant | None:
        stmt = select(TripParticipant).where(
            TripParticipant.trip_id == trip_id,
            TripParticipant.spender_id == spender_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, participant: TripParticipant) -> TripParticipant:
        self.db.add(participant)
        self.db.commit()
        self.db.refresh(participant)
        return participant

    def delete(self, participant: TripParticipant) -> None:
        self.db.delete(participant)
        self.db.commit()


class TripExpenseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_trip(self, trip_id: UUID, user_id: UUID) -> list[TripExpense]:
        stmt = (
            select(TripExpense)
            .options(
                selectinload(TripExpense.shares).selectinload(TripExpenseShare.spender),
                selectinload(TripExpense.paid_by),
            )
            .where(TripExpense.trip_id == trip_id, TripExpense.user_id == user_id)
            .order_by(TripExpense.data.asc(), TripExpense.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id(self, expense_id: UUID, user_id: UUID) -> TripExpense | None:
        stmt = (
            select(TripExpense)
            .options(
                selectinload(TripExpense.shares).selectinload(TripExpenseShare.spender),
                selectinload(TripExpense.paid_by),
            )
            .where(TripExpense.id == expense_id, TripExpense.user_id == user_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, expense: TripExpense) -> TripExpense:
        self.db.add(expense)
        self.db.commit()
        self.db.refresh(expense)
        return expense

    def update(self, expense: TripExpense) -> TripExpense:
        self.db.commit()
        self.db.refresh(expense)
        return expense

    def delete(self, expense: TripExpense) -> None:
        self.db.delete(expense)
        self.db.commit()


class TripExpenseShareRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_expense(self, expense_id: UUID) -> list[TripExpenseShare]:
        stmt = (
            select(TripExpenseShare)
            .options(selectinload(TripExpenseShare.spender))
            .where(TripExpenseShare.trip_expense_id == expense_id)
            .order_by(TripExpenseShare.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def delete_for_expense(self, expense_id: UUID) -> None:
        stmt = delete(TripExpenseShare).where(TripExpenseShare.trip_expense_id == expense_id)
        self.db.execute(stmt)
        self.db.commit()

    def create_many(self, rows: list[TripExpenseShare]) -> list[TripExpenseShare]:
        for r in rows:
            self.db.add(r)
        self.db.commit()
        for r in rows:
            self.db.refresh(r)
        return rows
