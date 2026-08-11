import traceback
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import decode_token
from app.database.connection import SessionLocal
from app.models.system_error_log import SystemErrorLog
from app.repositories.system_error_log_repository import SystemErrorLogRepository

_SKIP_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json")


def _should_log(path: str) -> bool:
    return not any(path.startswith(p) for p in _SKIP_PREFIXES)


def _user_id_from_request(request: Request) -> UUID | None:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    sub = decode_token(token)
    if sub is None:
        return None
    try:
        return UUID(sub)
    except ValueError:
        return None


def _persist_error(
    *,
    method: str,
    path: str,
    status_code: int,
    detail: str | None,
    tb: str | None,
    user_id: UUID | None,
) -> None:
    db = SessionLocal()
    try:
        SystemErrorLogRepository(db).create(
            SystemErrorLog(
                method=method[:16],
                path=path[:512],
                status_code=status_code,
                detail=detail,
                traceback=tb,
                user_id=user_id,
            )
        )
    except Exception:
        db.rollback()
    finally:
        db.close()


class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not _should_log(request.url.path):
            return await call_next(request)

        user_id = _user_id_from_request(request)
        try:
            response = await call_next(request)
        except Exception as exc:
            _persist_error(
                method=request.method,
                path=request.url.path,
                status_code=500,
                detail=str(exc)[:4000] or type(exc).__name__,
                tb=traceback.format_exc()[:8000],
                user_id=user_id,
            )
            raise

        if response.status_code >= 400:
            detail = None
            if hasattr(response, "body") and response.status_code < 500:
                detail = f"HTTP {response.status_code}"
            _persist_error(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                detail=detail,
                tb=None,
                user_id=user_id,
            )
        return response
