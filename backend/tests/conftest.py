"""Shared pytest fixtures.

Each test runs against an isolated in-memory SQLite database to keep tests
fast and side-effect free.
"""

from __future__ import annotations

import os

# Force an in-memory SQLite database for the test process before app imports.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import database as db_module
from app.core.database import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    """A FastAPI TestClient backed by an isolated in-memory SQLite database."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TestSessionLocal = sessionmaker(
        bind=test_engine, autocommit=False, autoflush=False, future=True
    )

    # Ensure all models are imported so metadata is fully populated.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    # Also point the module-level engine at the in-memory one so any code
    # that uses `db_module.engine` directly stays consistent in tests.
    original_engine = db_module.engine
    db_module.engine = test_engine

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    db_module.engine = original_engine
    Base.metadata.drop_all(bind=test_engine)
