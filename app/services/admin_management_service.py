from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_access_log import UserAccessLog
from app.repositories.system_error_log_repository import SystemErrorLogRepository
from app.repositories.user_access_log_repository import UserAccessLogRepository
from app.repositories.user_repository import UserRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AdminManagementService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.access_logs = UserAccessLogRepository(db)
        self.error_logs = SystemErrorLogRepository(db)

    def record_login(self, user: User) -> None:
        user.login_count = (user.login_count or 0) + 1
        user.last_login_at = _utc_now()
        self.db.add(UserAccessLog(user_id=user.id, event_type="login"))
        self.db.commit()

    def get_stats(self) -> dict:
        now = _utc_now()
        since_7d = now - timedelta(days=7)
        since_30d = now - timedelta(days=30)

        total_registered = int(
            self.db.execute(select(func.count()).select_from(User)).scalar_one()
        )
        registered_last_7d = int(
            self.db.execute(
                select(func.count()).select_from(User).where(User.created_at >= since_7d)
            ).scalar_one()
        )
        registered_last_30d = int(
            self.db.execute(
                select(func.count()).select_from(User).where(User.created_at >= since_30d)
            ).scalar_one()
        )
        users_ever_logged_in = int(
            self.db.execute(
                select(func.count()).select_from(User).where(User.login_count > 0)
            ).scalar_one()
        )
        active_last_7d = int(
            self.db.execute(
                select(func.count()).select_from(User).where(User.last_login_at >= since_7d)
            ).scalar_one()
        )
        logins_last_7d = self.access_logs.count_logins_since(since_7d)
        logins_last_30d = self.access_logs.count_logins_since(since_30d)
        errors_last_7d = self.error_logs.count_since(since_7d)
        errors_last_30d = self.error_logs.count_since(since_30d)

        return {
            "total_registered": total_registered,
            "registered_last_7d": registered_last_7d,
            "registered_last_30d": registered_last_30d,
            "users_ever_logged_in": users_ever_logged_in,
            "active_users_last_7d": active_last_7d,
            "logins_last_7d": logins_last_7d,
            "logins_last_30d": logins_last_30d,
            "errors_last_7d": errors_last_7d,
            "errors_last_30d": errors_last_30d,
        }

    def list_error_logs(self, *, limit: int = 200) -> list[dict]:
        rows = self.error_logs.list_recent(limit=limit)
        user_ids = {r.user_id for r in rows if r.user_id is not None}
        emails: dict[UUID, str] = {}
        if user_ids:
            users = self.db.execute(select(User).where(User.id.in_(user_ids))).scalars().all()
            emails = {u.id: u.email for u in users}

        return [
            {
                "id": str(r.id),
                "created_at": r.created_at.isoformat(),
                "method": r.method,
                "path": r.path,
                "status_code": r.status_code,
                "detail": r.detail,
                "traceback": r.traceback,
                "user_id": str(r.user_id) if r.user_id else None,
                "user_email": emails.get(r.user_id) if r.user_id else None,
            }
            for r in rows
        ]
