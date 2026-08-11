from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.error_logging import ErrorLoggingMiddleware
from app.database.base import Base
from app.database.connection import engine
from app.database.migrations import run_alembic_upgrade
from app.database.schema_patches import apply_sqlite_schema_patches, ensure_platform_settings, repair_goal_pool_data_consistency
from app.database.url import is_postgresql_url
import app.models  # noqa: F401 — register models for create_all

from app.expenses.router import router as expenses_router
from app.trips.router import router as trips_router
from app.routers import (
    auth_router,
    budget_router,
    card_router,
    card_transaction_router,
    category_router,
    dashboard_router,
    debtor_router,
    goal_router,
    income_router,
    installment_router,
    investment_router,
    notification_router,
    period_router,
    reports_router,
    spender_router,
    statement_import_router,
    transfer_router,
    user_router,
    admin_management_router,
    settings_router,
)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    if is_postgresql_url(settings.DATABASE_URL):
        if settings.RUN_MIGRATIONS_ON_STARTUP:
            logger.info("Aplicando migrações Alembic (PostgreSQL)...")
            run_alembic_upgrade()
        else:
            logger.info(
                "Migrações Alembic ignoradas no startup (RUN_MIGRATIONS_ON_STARTUP=false). "
                "Rode manualmente: python -m alembic upgrade head"
            )
    else:
        Base.metadata.create_all(bind=engine)
        apply_sqlite_schema_patches(engine)
    ensure_platform_settings(engine)
    repair_goal_pool_data_consistency(engine)
    yield


app = FastAPI(
    title="BomFin Planejamento Financeiro API",
    description="Personal finance control API — modular FastAPI backend.",
    version="0.1.0",
    lifespan=lifespan,
)

_settings = get_settings()
_cors_raw = (_settings.CORS_ORIGINS or "").strip()
_cors_origins = (
    [o.strip() for o in _cors_raw.split(",") if o.strip()] if _cors_raw else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ErrorLoggingMiddleware)

API_PREFIX = "/api/v1"

app.include_router(auth_router.router, prefix=API_PREFIX)
app.include_router(admin_management_router.router, prefix=API_PREFIX)
app.include_router(settings_router.router, prefix=API_PREFIX)
app.include_router(user_router.router, prefix=API_PREFIX)
app.include_router(period_router.router, prefix=API_PREFIX)
app.include_router(category_router.router, prefix=API_PREFIX)
app.include_router(income_router.router, prefix=API_PREFIX)
app.include_router(expenses_router, prefix=API_PREFIX)
app.include_router(installment_router.router, prefix=API_PREFIX)
app.include_router(card_router.router, prefix=API_PREFIX)
app.include_router(spender_router.router, prefix=API_PREFIX)
app.include_router(card_transaction_router.router, prefix=API_PREFIX)
app.include_router(budget_router.router, prefix=API_PREFIX)
app.include_router(goal_router.router, prefix=API_PREFIX)
app.include_router(transfer_router.router, prefix=API_PREFIX)
app.include_router(dashboard_router.router, prefix=API_PREFIX)
app.include_router(reports_router.router, prefix=API_PREFIX)
app.include_router(investment_router.router, prefix=API_PREFIX)
app.include_router(debtor_router.router, prefix=API_PREFIX)
app.include_router(statement_import_router.router, prefix=API_PREFIX)
app.include_router(trips_router, prefix=API_PREFIX)
app.include_router(notification_router.router, prefix=API_PREFIX)


@app.get("/health")
def health():
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": str(exc)},
        )
    return {"status": "ok", "database": "connected"}
