from uuid import UUID

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.period import Period


class PeriodRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, period_id: UUID, user_id: UUID) -> Period | None:
        p = self.db.get(Period, period_id)
        if p is None or p.user_id != user_id:
            return None
        return p

    def list_by_user(self, user_id: UUID) -> list[Period]:
        stmt: Select[tuple[Period]] = select(Period).where(Period.user_id == user_id).order_by(Period.ano, Period.mes)
        return list(self.db.execute(stmt).scalars().all())

    def get_by_month_year(self, user_id: UUID, mes: int, ano: int) -> Period | None:
        stmt = select(Period).where(
            Period.user_id == user_id,
            Period.mes == mes,
            Period.ano == ano,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_or_create_month_year(self, user_id: UUID, mes: int, ano: int) -> Period:
        existing = self.get_by_month_year(user_id, mes, ano)
        if existing is not None:
            return existing
        try:
            return self.create(Period(mes=mes, ano=ano, status="open", user_id=user_id))
        except IntegrityError:
            self.db.rollback()
            existing = self.get_by_month_year(user_id, mes, ano)
            if existing is None:
                raise
            return existing

    def get_previous_calendar_month(self, user_id: UUID, mes: int, ano: int) -> Period | None:
        """Mês civil anterior (jan/2026 → dez/2025)."""
        if mes > 1:
            return self.get_by_month_year(user_id, mes - 1, ano)
        return self.get_by_month_year(user_id, 12, ano - 1)

    def create_many(self, periods: list[Period]) -> list[Period]:
        for p in periods:
            self.db.add(p)
        self.db.commit()
        for p in periods:
            self.db.refresh(p)
        return periods

    def create(self, period: Period) -> Period:
        self.db.add(period)
        self.db.commit()
        self.db.refresh(period)
        return period

    def update(self, period: Period) -> Period:
        self.db.commit()
        self.db.refresh(period)
        return period

    def periods_after(self, user_id: UUID, ano: int, mes: int) -> list[Period]:
        stmt = (
            select(Period)
            .where(Period.user_id == user_id)
            .where(or_(Period.ano > ano, and_(Period.ano == ano, Period.mes > mes)))
            .order_by(Period.ano, Period.mes)
        )
        return list(self.db.execute(stmt).scalars().all())

    def consecutive_from(self, user_id: UUID, start_period_id: UUID, count: int) -> list[Period]:
        if count <= 0:
            return []
        ordered = self.list_by_user(user_id)
        idx = next((i for i, p in enumerate(ordered) if p.id == start_period_id), -1)
        if idx < 0:
            return []
        return ordered[idx : idx + count]
