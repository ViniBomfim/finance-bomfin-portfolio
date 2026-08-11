from pydantic import BaseModel


class AdminManagementStats(BaseModel):
    total_registered: int
    registered_last_7d: int
    registered_last_30d: int
    users_ever_logged_in: int
    active_users_last_7d: int
    logins_last_7d: int
    logins_last_30d: int
    errors_last_7d: int
    errors_last_30d: int


class SystemErrorLogRow(BaseModel):
    id: str
    created_at: str
    method: str
    path: str
    status_code: int
    detail: str | None
    traceback: str | None
    user_id: str | None
    user_email: str | None
