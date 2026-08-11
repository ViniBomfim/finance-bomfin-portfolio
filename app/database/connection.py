from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.database.url import is_postgresql_url

settings = get_settings()

connect_args: dict[str, object] = {}
engine_kwargs: dict[str, object] = {}

if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
elif is_postgresql_url(settings.DATABASE_URL):
    # connect_timeout também vai na URL (normalize_database_url); reforço no driver.
    connect_args["connect_timeout"] = 15
    engine_kwargs.update(
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=300,
    )

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, **engine_kwargs)


@event.listens_for(engine, "connect")
def _set_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    if engine.dialect.name == "sqlite":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
