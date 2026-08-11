from app.database.url import normalize_database_url


def test_normalize_postgresql_uri_to_psycopg2() -> None:
    url = "postgresql://user:pass@db.example.com:5432/postgres"
    assert normalize_database_url(url) == (
        "postgresql+psycopg2://user:pass@db.example.com:5432/postgres"
        "?sslmode=require&connect_timeout=15"
    )


def test_normalize_postgres_scheme_alias() -> None:
    url = "postgres://user:pass@db.example.com:5432/postgres"
    assert normalize_database_url(url).startswith("postgresql+psycopg2://")


def test_normalize_preserves_existing_sslmode() -> None:
    url = "postgresql://user:pass@db.example.com:5432/postgres?sslmode=disable"
    assert normalize_database_url(url) == (
        "postgresql+psycopg2://user:pass@db.example.com:5432/postgres"
        "?sslmode=disable&connect_timeout=15"
    )


def test_normalize_preserves_existing_connect_timeout() -> None:
    url = "postgresql://user:pass@db.example.com:5432/postgres?sslmode=require&connect_timeout=5"
    assert normalize_database_url(url) == (
        "postgresql+psycopg2://user:pass@db.example.com:5432/postgres"
        "?sslmode=require&connect_timeout=5"
    )


def test_normalize_sqlite_unchanged() -> None:
    url = "sqlite:///./finance_manager.db"
    assert normalize_database_url(url) == url


def test_normalize_encodes_password_with_at_sign() -> None:
    url = "postgresql://postgres:Senha@123@db.example.com:5432/postgres"
    normalized = normalize_database_url(url)
    assert "Senha%40123" in normalized
    assert normalized.startswith("postgresql+psycopg2://postgres:Senha%40123@db.example.com:5432/postgres")
    assert "connect_timeout=15" in normalized
