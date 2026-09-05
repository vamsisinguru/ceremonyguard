"""Tests for the SQLAlchemy database foundation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.database import Base, get_db
from app.models import (
    AuditEvent,
    Ceremony,
    CeremonyAttempt,
    Contribution,
    Participant,
)
from fastapi.testclient import TestClient


def test_get_db_yields_session(client: TestClient) -> None:
    """The get_db dependency should yield a usable SQLAlchemy Session."""
    db_iter = get_db()
    session = next(db_iter)
    try:
        assert isinstance(session, Session)
        # A trivial query should succeed.
        result = session.execute(__import__("sqlalchemy").text("SELECT 1")).scalar()
        assert result == 1
    finally:
        try:
            next(db_iter)
        except StopIteration:
            pass


def test_all_tables_created(client: TestClient) -> None:
    """All foundation tables should be present in the database."""
    inspector = inspect(client.app.dependency_overrides[get_db]().__next__().bind)
    tables = set(inspector.get_table_names())
    expected = {
        "ceremonies",
        "participants",
        "ceremony_attempts",
        "contributions",
        "audit_events",
    }
    assert expected.issubset(tables)


def test_can_persist_foundation_entities(client: TestClient) -> None:
    """A round-trip of all foundation entities should persist correctly."""
    db = client.app.dependency_overrides[get_db]().__next__()

    ceremony = Ceremony(name="Test Ceremony", status="created")
    db.add(ceremony)
    db.commit()
    db.refresh(ceremony)

    participant = Participant(ceremony_id=ceremony.id, name="Alice")
    db.add(participant)

    attempt = CeremonyAttempt(ceremony_id=ceremony.id, attempt_number=1)
    db.add(attempt)
    db.commit()
    db.refresh(participant)
    db.refresh(attempt)

    contribution = Contribution(
        ceremony_id=ceremony.id,
        attempt_id=attempt.id,
        participant_id=participant.id,
        contribution_hash="abc123",
        contribution_data="sample-data",
    )
    db.add(contribution)

    audit = AuditEvent(
        ceremony_id=ceremony.id,
        participant_id=participant.id,
        event_type="participant_registered",
        message="Alice registered",
    )
    db.add(audit)
    db.commit()

    assert ceremony.id is not None
    assert participant.id is not None
    assert attempt.id is not None
    assert contribution.id is not None
    assert audit.id is not None
    assert isinstance(ceremony.created_at, datetime)
