"""SQLAlchemy engine/session setup. Works with SQLite (dev/tests) and SQL Server (pyodbc)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

settings = get_settings()
_url = settings.database_url

if _url.startswith("sqlite"):
    kwargs: dict = {"connect_args": {"check_same_thread": False}}
    if _url in ("sqlite://", "sqlite:///:memory:"):
        kwargs["poolclass"] = StaticPool  # keep one shared in-memory DB (used by tests)
    engine = create_engine(_url, **kwargs)
else:
    engine = create_engine(_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
