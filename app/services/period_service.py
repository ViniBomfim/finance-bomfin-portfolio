from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.period import Period
from app.repositories.period_repository import PeriodRepository


def _advance_calendar_month(mes: int, ano: int) -> tuple[int, int]:
    if mes < 12:
        return mes + 1, ano
    return 1, ano + 1


class PeriodService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.periods = PeriodRepository(db)

    def list_periods(self, user_id: UUID) -> list[Period]:
        return self.periods.list_by_user(user_id)

    def get(self, user_id: UUID, period_id: UUID) -> Period:
        p = self.periods.get_by_id(period_id, user_id)
        if p is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        return p

    def create_year(self, user_id: UUID, ano: int) -> list[Period]:
        created: list[Period] = []
        for mes in range(1, 13):
            created.append(self.periods.get_or_create_month_year(user_id, mes, ano))
        return created

    def ensure_calendar_periods_from_start(
        self, user_id: UUID, start_period_id: UUID, count: int
    ) -> list[Period]:
        """Garante `count` meses civis consecutivos a partir do período inicial (cria meses em falta)."""
        if count <= 0:
            return []
        start = self.periods.get_by_id(start_period_id, user_id)
        if start is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
        out: list[Period] = []
        mes, ano = start.mes, start.ano
        for _ in range(count):
            out.append(self.periods.get_or_create_month_year(user_id, mes, ano))
            mes, ano = _advance_calendar_month(mes, ano)
        return out

    def close_period(self, user_id: UUID, period_id: UUID) -> Period:
        p = self.get(user_id, period_id)
        p.status = "closed"
        return self.periods.update(p)

    def reopen_period(self, user_id: UUID, period_id: UUID) -> Period:
        p = self.get(user_id, period_id)
        p.status = "open"
        return self.periods.update(p)
