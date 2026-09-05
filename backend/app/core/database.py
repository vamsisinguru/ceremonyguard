"""SQLAlchemy database engine and session setup.

Uses SQLite by default. The engine is created with `check_same_thread=False`
so it can be used safely with FastAPI's threaded request handling.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""


def _build_engine() -> Engine:
    connect_args = (
        {"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {}
    )
    return create_engine(
        settings.database_url,
        echo=settings.db_echo,
        connect_args=connect_args,
        future=True,
    )


engine: Engine = _build_engine()
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
    expire_on_commit=False,
)


def get_db() -> Session:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables defined on the declarative base."""
    # Import here so models are registered on Base.metadata before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
