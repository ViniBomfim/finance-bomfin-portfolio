"""Regras de alteração quando o período está fechado."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.period_repository import PeriodRepository

CLOSED_DETAIL = "Período fechado: alterações não são permitidas."


def is_period_mutable(db: Session, user_id: UUID, period_id: UUID) -> bool:
    """Retorna True se o período existe, pertence ao usuário e está aberto para escrita."""
    p = PeriodRepository(db).get_by_id(period_id, user_id)
    return p is not None and p.status == "open"


def ensure_period_mutable(db: Session, user_id: UUID, period_id: UUID) -> None:
    """Garante que o período existe, pertence ao usuário e está aberto para escrita."""
    repo = PeriodRepository(db)
    p = repo.get_by_id(period_id, user_id)
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
    if p.status != "open":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=CLOSED_DETAIL)
