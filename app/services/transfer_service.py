from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.transfer import Transfer
from app.repositories.goal_repository import GoalRepository
from app.repositories.transfer_repository import TransferRepository
from app.schemas.transfer_schema import TransferCreate


class TransferService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.transfers = TransferRepository(db)
        self.goals = GoalRepository(db)

    def create(self, user_id: UUID, data: TransferCreate) -> Transfer:
        if data.destination_type == "goal" and data.destination_id is not None:
            g = self.goals.get_by_id(data.destination_id, user_id)
            if g is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination goal not found")
            if data.source_type == "balance":
                g.valor_atual += data.valor
                self.goals.update(g)
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported source for goal transfer")
        elif data.source_type == "goal" and data.source_id is not None:
            g = self.goals.get_by_id(data.source_id, user_id)
            if g is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source goal not found")
            if g.valor_atual < data.valor:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient goal balance")
            g.valor_atual -= data.valor
            self.goals.update(g)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported transfer types")

        t = Transfer(
            source_type=data.source_type,
            source_id=data.source_id,
            destination_type=data.destination_type,
            destination_id=data.destination_id,
            valor=data.valor,
            data=data.data,
            user_id=user_id,
        )
        return self.transfers.create(t)

    def list_transfers(self, user_id: UUID) -> list[Transfer]:
        return self.transfers.list_by_user(user_id)
