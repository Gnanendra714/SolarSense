from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def normalize_database_url(raw_url: str) -> str:
    """Normalize provider PostgreSQL URLs to the explicitly installed Psycopg 3 driver."""
    if raw_url.startswith("postgres://"):
        return "postgresql+psycopg://" + raw_url[len("postgres://"):]
    if raw_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw_url[len("postgresql://"):]
    return raw_url


database_url = normalize_database_url(settings.database_url)
parsed_url = make_url(database_url)

if parsed_url.get_backend_name() == "sqlite":
    database_path = parsed_url.database
    if database_path and database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"connect_timeout": 10},
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
