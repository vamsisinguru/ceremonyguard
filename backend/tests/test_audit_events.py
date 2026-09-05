"""Tests for audit event recording on Phase 2 operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AuditEvent
from fastapi.testclient import TestClient

from tests.helpers import (
    create_attempt,
    create_ceremony,
    create_participant,
    submit_contribution,
)


def _get_session(client: TestClient) -> Session:
    return client.app.dependency_overrides[get_db]().__next__()


def test_ceremony_creation_creates_audit_event(client: TestClient) -> None:
    ceremony = create_ceremony(client, "Audited Ceremony")
    db = _get_session(client)
    events = list(
        db.scalars(
            select(AuditEvent).where(AuditEvent.ceremony_id == ceremony["id"])
        )
    )
    types = [e.event_type for e in events]
    assert "ceremony_created" in types


def test_participant_creation_creates_audit_event(client: TestClient) -> None:
    ceremony = create_ceremony(client, "Audited Participant")
    participant = create_participant(client, ceremony["id"], "Alice")
    db = _get_session(client)
    events = list(
        db.scalars(
            select(AuditEvent).where(AuditEvent.ceremony_id == ceremony["id"])
        )
    )
    types = [e.event_type for e in events]
    assert "participant_created" in types
    participant_event = next(e for e in events if e.event_type == "participant_created")
    assert participant_event.participant_id == participant["id"]


def test_attempt_creation_creates_audit_event(client: TestClient) -> None:
    ceremony = create_ceremony(client, "Audited Attempt")
    create_attempt(client, ceremony["id"])
    db = _get_session(client)
    events = list(
        db.scalars(
            select(AuditEvent).where(AuditEvent.ceremony_id == ceremony["id"])
        )
    )
    types = [e.event_type for e in events]
    assert "attempt_created" in types


def test_contribution_submission_creates_audit_event(client: TestClient) -> None:
    ceremony = create_ceremony(client, "Audited Contribution")
    participant = create_participant(client, ceremony["id"], "Alice")
    attempt = create_attempt(client, ceremony["id"])
    submit_contribution(client, ceremony["id"], attempt["id"], participant["id"], "x")

    db = _get_session(client)
    events = list(
        db.scalars(
            select(AuditEvent).where(AuditEvent.ceremony_id == ceremony["id"])
        )
    )
    types = [e.event_type for e in events]
    assert "contribution_submitted" in types
    contribution_event = next(
        e for e in events if e.event_type == "contribution_submitted"
    )
    assert contribution_event.participant_id == participant["id"]
