from app.database.session import normalize_database_url


def test_normalizes_render_postgres_scheme():
    assert normalize_database_url("postgres://user:pass@host/db") == (
        "postgresql+psycopg://user:pass@host/db"
    )


def test_normalizes_postgresql_scheme():
    assert normalize_database_url("postgresql://user:pass@host/db") == (
        "postgresql+psycopg://user:pass@host/db"
    )


def test_keeps_sqlite_url():
    assert normalize_database_url("sqlite:///./data/test.db") == "sqlite:///./data/test.db"
