from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, desc, func, select
from sqlalchemy.orm import Session

from app.models.user_access_log import UserAccessLog


class UserAccessLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, user_id: UUID, event_type: str) -> UserAccessLog:
        row = UserAccessLog(user_id=user_id, event_type=event_type)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def count_logins_since(self, since: datetime) -> int:
        stmt = (
            select(func.count())
            .select_from(UserAccessLog)
            .where(UserAccessLog.event_type == "login", UserAccessLog.created_at >= since)
        )
        return int(self.db.execute(stmt).scalar_one())

    def distinct_users_since(self, since: datetime) -> int:
        stmt = (
            select(func.count(func.distinct(UserAccessLog.user_id)))
            .select_from(UserAccessLog)
            .where(UserAccessLog.created_at >= since)
        )
        return int(self.db.execute(stmt).scalar_one())

    def list_recent(self, *, limit: int = 50) -> list[UserAccessLog]:
        stmt: Select[tuple[UserAccessLog]] = (
            select(UserAccessLog).order_by(desc(UserAccessLog.created_at)).limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
