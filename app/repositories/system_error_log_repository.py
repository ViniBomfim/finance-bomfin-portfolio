from uuid import UUID

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from app.models.system_error_log import SystemErrorLog


class SystemErrorLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, row: SystemErrorLog) -> SystemErrorLog:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_recent(self, *, limit: int = 200) -> list[SystemErrorLog]:
        stmt: Select[tuple[SystemErrorLog]] = (
            select(SystemErrorLog).order_by(desc(SystemErrorLog.created_at)).limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_since(self, since) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(SystemErrorLog).where(SystemErrorLog.created_at >= since)
        return int(self.db.execute(stmt).scalar_one())
