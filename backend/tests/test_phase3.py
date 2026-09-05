"""Phase 3 tests — duplicate and conflict detection."""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AuditEvent, Contribution
from fastapi.testclient import TestClient

from tests.helpers import (
    create_attempt,
    create_ceremony,
    create_participant,
    submit_contribution,
    submit_contribution_raw,
)


def _setup(client: TestClient, ceremony_name: str = "Phase 3 Ceremony"):
    """Create a ceremony, one participant, and one attempt."""
    ceremony = create_ceremony(client, ceremony_name)
    participant = create_participant(client, ceremony["id"], "Alice")
    attempt = create_attempt(client, ceremony["id"])
    return ceremony, participant, attempt


def _get_session(client: TestClient) -> Session:
    return client.app.dependency_overrides[get_db]().__next__()


def _count_accepted(db: Session, ceremony_id: int, participant_id: int) -> int:
    return len(
        list(
            db.scalars(
                select(Contribution).where(
                    Contribution.ceremony_id == ceremony_id,
                    Contribution.participant_id == participant_id,
                    Contribution.status == "accepted",
                )
            )
        )
    )


# --------------------------------------------------------------------------- #
# NORMAL: first contribution accepted
# --------------------------------------------------------------------------- #
def test_first_contribution_is_accepted(client: TestClient) -> None:
    ceremony, participant, attempt = _setup(client)
    response = submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-A"
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "accepted"
    assert body["contribution"]["status"] == "accepted"
    assert body["contribution"]["id"] > 0


# --------------------------------------------------------------------------- #
# DUPLICATE
# --------------------------------------------------------------------------- #
def test_duplicate_same_data_twice(client: TestClient) -> None:
    """Same participant submits exactly the same contribution twice."""
    ceremony, participant, attempt = _setup(client)
    r1 = submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-X"
    )
    r2 = submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-X"
    )
    assert r1.status_code == 201
    assert r2.status_code == 200

    b1 = r1.json()
    b2 = r2.json()
    assert b1["status"] == "accepted"
    assert b2["status"] == "duplicate"

    # Only one canonical accepted contribution exists.
    db = _get_session(client)
    assert _count_accepted(db, ceremony["id"], participant["id"]) == 1


def test_duplicate_response_contains_useful_info(client: TestClient) -> None:
    ceremony, participant, attempt = _setup(client)
    submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-D"
    )
    r2 = submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-D"
    )
    body = r2.json()
    assert body["status"] == "duplicate"
    assert body["ceremony_id"] == ceremony["id"]
    assert body["participant_id"] == participant["id"]
    assert body["contribution"]["id"] > 0  # original contribution ID
    assert body["submitted_hash"]  # hash of the duplicate submission
    assert "retained" in body["message"].lower()


def test_duplicate_creates_audit_event(client: TestClient) -> None:
    ceremony, participant, attempt = _setup(client)
    submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-D"
    )
    submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-D"
    )
    db = _get_session(client)
    events = list(
        db.scalars(
            select(AuditEvent).where(AuditEvent.ceremony_id == ceremony["id"])
        )
    )
    types = [e.event_type for e in events]
    assert "CONTRIBUTION_DUPLICATE" in types


# --------------------------------------------------------------------------- #
# CONFLICT
# --------------------------------------------------------------------------- #
def test_conflict_different_data(client: TestClient) -> None:
    """Participant submits A (accepted), then different B (conflict)."""
    ceremony, participant, attempt = _setup(client)
    r1 = submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-A"
    )
    r2 = submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-B"
    )
    assert r1.status_code == 201
    assert r2.status_code == 409

    b1 = r1.json()
    b2 = r2.json()
    assert b1["status"] == "accepted"
    assert b2["status"] == "conflict"


def test_conflict_original_remains_canonical(client: TestClient) -> None:
    ceremony, participant, attempt = _setup(client)
    r1 = submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-A"
    )
    submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-B"
    )
    original_id = r1.json()["contribution"]["id"]

    # The canonical contribution is still the original.
    db = _get_session(client)
    accepted = list(
        db.scalars(
            select(Contribution).where(
                Contribution.ceremony_id == ceremony["id"],
                Contribution.participant_id == participant["id"],
                Contribution.status == "accepted",
            )
        )
    )
    assert len(accepted) == 1
    assert accepted[0].id == original_id
    assert accepted[0].contribution_data == "data-A"


def test_conflict_does_not_replace_original(client: TestClient) -> None:
    ceremony, participant, attempt = _setup(client)
    r1 = submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-A"
    )
    r2 = submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-B"
    )
    b1 = r1.json()
    b2 = r2.json()
    # The conflict response returns the original as the canonical contribution.
    assert b2["contribution"]["id"] == b1["contribution"]["id"]
    assert b2["contribution"]["contribution_hash"] == b1["contribution"]["contribution_hash"]
    # The submitted hash is different (it's the conflicting one).
    assert b2["submitted_hash"] != b2["contribution"]["contribution_hash"]


def test_conflict_response_contains_useful_info(client: TestClient) -> None:
    ceremony, participant, attempt = _setup(client)
    submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-A"
    )
    r2 = submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-B"
    )
    body = r2.json()
    assert body["status"] == "conflict"
    assert body["ceremony_id"] == ceremony["id"]
    assert body["participant_id"] == participant["id"]
    assert body["contribution"]["id"] > 0  # original contribution ID
    assert body["contribution"]["contribution_hash"]  # original hash
    assert body["submitted_hash"]  # conflicting hash
    assert body["submitted_hash"] != body["contribution"]["contribution_hash"]
    assert "retained" in body["message"].lower()


def test_conflict_creates_audit_event(client: TestClient) -> None:
    ceremony, participant, attempt = _setup(client)
    submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-A"
    )
    submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-B"
    )
    db = _get_session(client)
    events = list(
        db.scalars(
            select(AuditEvent).where(AuditEvent.ceremony_id == ceremony["id"])
        )
    )
    types = [e.event_type for e in events]
    assert "CONTRIBUTION_CONFLICT" in types


# --------------------------------------------------------------------------- #
# MULTIPLE PARTICIPANTS
# --------------------------------------------------------------------------- #
def test_multiple_participants_each_one_canonical(client: TestClient) -> None:
    ceremony = create_ceremony(client, "Multi Participant")
    attempt = create_attempt(client, ceremony["id"])
    pa = create_participant(client, ceremony["id"], "A")
    pb = create_participant(client, ceremony["id"], "B")
    pc = create_participant(client, ceremony["id"], "C")

    ra = submit_contribution_raw(client, ceremony["id"], attempt["id"], pa["id"], "A1")
    rb = submit_contribution_raw(client, ceremony["id"], attempt["id"], pb["id"], "B1")
    rc = submit_contribution_raw(client, ceremony["id"], attempt["id"], pc["id"], "C1")

    assert ra.status_code == 201
    assert rb.status_code == 201
    assert rc.status_code == 201
    assert ra.json()["status"] == "accepted"
    assert rb.json()["status"] == "accepted"
    assert rc.json()["status"] == "accepted"

    db = _get_session(client)
    for p in [pa, pb, pc]:
        assert _count_accepted(db, ceremony["id"], p["id"]) == 1


# --------------------------------------------------------------------------- #
# CEREMONY ISOLATION
# --------------------------------------------------------------------------- #
def test_same_participant_independent_in_two_ceremonies(client: TestClient) -> None:
    """Same participant can submit in Ceremony 1 and Ceremony 2 independently."""
    c1 = create_ceremony(client, "Ceremony 1")
    c2 = create_ceremony(client, "Ceremony 2")
    p1 = create_participant(client, c1["id"], "Shared")
    p2 = create_participant(client, c2["id"], "Shared")
    a1 = create_attempt(client, c1["id"])
    a2 = create_attempt(client, c2["id"])

    r1 = submit_contribution_raw(client, c1["id"], a1["id"], p1["id"], "data-1")
    r2 = submit_contribution_raw(client, c2["id"], a2["id"], p2["id"], "data-2")
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["status"] == "accepted"
    assert r2.json()["status"] == "accepted"

    # Ceremony 1 contribution does not affect Ceremony 2.
    db = _get_session(client)
    assert _count_accepted(db, c1["id"], p1["id"]) == 1
    assert _count_accepted(db, c2["id"], p2["id"]) == 1


def test_ceremony2_attempt_cannot_be_used_for_ceremony1(client: TestClient) -> None:
    """An attempt belonging to Ceremony 2 cannot be used for a Ceremony 1 contribution."""
    c1 = create_ceremony(client, "Isolation A")
    c2 = create_ceremony(client, "Isolation B")
    p1 = create_participant(client, c1["id"], "Alice")
    a2 = create_attempt(client, c2["id"])

    response = submit_contribution_raw(
        client, c1["id"], a2["id"], p1["id"], "data"
    )
    assert response.status_code == 400
    assert "ceremony" in response.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# ATTEMPT BEHAVIOR
# --------------------------------------------------------------------------- #
def test_retry_in_another_attempt_does_not_create_second_canonical(client: TestClient) -> None:
    """Same participant retrying in a second attempt must not create a second
    canonical contribution for the same ceremony."""
    ceremony = create_ceremony(client, "Cross Attempt")
    participant = create_participant(client, ceremony["id"], "Alice")
    a1 = create_attempt(client, ceremony["id"])
    a2 = create_attempt(client, ceremony["id"])

    r1 = submit_contribution_raw(
        client, ceremony["id"], a1["id"], participant["id"], "data-A"
    )
    r2 = submit_contribution_raw(
        client, ceremony["id"], a2["id"], participant["id"], "data-B"
    )
    assert r1.status_code == 201
    assert r2.status_code == 409
    assert r1.json()["status"] == "accepted"
    assert r2.json()["status"] == "conflict"

    db = _get_session(client)
    assert _count_accepted(db, ceremony["id"], participant["id"]) == 1


def test_original_contribution_remains_traceable_across_attempts(client: TestClient) -> None:
    ceremony = create_ceremony(client, "Traceable")
    participant = create_participant(client, ceremony["id"], "Alice")
    a1 = create_attempt(client, ceremony["id"])
    a2 = create_attempt(client, ceremony["id"])

    r1 = submit_contribution_raw(
        client, ceremony["id"], a1["id"], participant["id"], "data-A"
    )
    original_id = r1.json()["contribution"]["id"]

    # Submit a conflict from a different attempt.
    r2 = submit_contribution_raw(
        client, ceremony["id"], a2["id"], participant["id"], "data-B"
    )
    # The conflict response still references the original canonical contribution.
    assert r2.json()["contribution"]["id"] == original_id

    # The original can be retrieved directly.
    fetched = client.get(f"/contributions/{original_id}").json()
    assert fetched["status"] == "accepted"
    assert fetched["contribution_data"] == "data-A"


# --------------------------------------------------------------------------- #
# HASH
# --------------------------------------------------------------------------- #
def test_same_data_produces_same_hash(client: TestClient) -> None:
    ceremony, participant, attempt = _setup(client)
    r1 = submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "identical"
    )
    r2 = submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "identical"
    )
    assert r1.json()["submitted_hash"] == r2.json()["submitted_hash"]
    expected = hashlib.sha256(b"identical").hexdigest()
    assert r1.json()["submitted_hash"] == expected


def test_different_data_produces_different_hash(client: TestClient) -> None:
    ceremony, participant, attempt = _setup(client)
    r1 = submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-1"
    )
    r2 = submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-2"
    )
    assert r1.json()["submitted_hash"] != r2.json()["submitted_hash"]


# --------------------------------------------------------------------------- #
# MAIN DEMO SCENARIO
# --------------------------------------------------------------------------- #
def test_main_demo_scenario(client: TestClient) -> None:
    """The main judge demonstration scenario.

    Ceremony created → A, B, C submit accepted contributions →
    simulated network failure → C retries with DIFFERENT data →
    CONFLICT → C1 remains canonical → audit event recorded.
    """
    ceremony = create_ceremony(client, "Demo Ceremony")
    attempt = create_attempt(client, ceremony["id"])

    pa = create_participant(client, ceremony["id"], "Participant A")
    pb = create_participant(client, ceremony["id"], "Participant B")
    pc = create_participant(client, ceremony["id"], "Participant C")

    # Each participant submits an accepted contribution.
    ra = submit_contribution_raw(client, ceremony["id"], attempt["id"], pa["id"], "A1")
    rb = submit_contribution_raw(client, ceremony["id"], attempt["id"], pb["id"], "B1")
    rc1 = submit_contribution_raw(client, ceremony["id"], attempt["id"], pc["id"], "C1")

    assert ra.status_code == 201
    assert rb.status_code == 201
    assert rc1.status_code == 201
    assert ra.json()["status"] == "accepted"
    assert rb.json()["status"] == "accepted"
    assert rc1.json()["status"] == "accepted"

    c1_id = rc1.json()["contribution"]["id"]

    # Simulated network failure → Participant C retries with DIFFERENT data.
    rc2 = submit_contribution_raw(client, ceremony["id"], attempt["id"], pc["id"], "C2")
    assert rc2.status_code == 409
    body = rc2.json()
    assert body["status"] == "conflict"

    # C1 remains canonical; C2 does NOT replace C1.
    assert body["contribution"]["id"] == c1_id
    assert body["contribution"]["contribution_data"] == "C1"

    db = _get_session(client)
    assert _count_accepted(db, ceremony["id"], pc["id"]) == 1

    # Audit event for CONTRIBUTION_CONFLICT is recorded.
    events = list(
        db.scalars(
            select(AuditEvent).where(AuditEvent.ceremony_id == ceremony["id"])
        )
    )
    types = [e.event_type for e in events]
    assert "CONTRIBUTION_CONFLICT" in types

    # Each participant has exactly one canonical contribution.
    for p in [pa, pb, pc]:
        assert _count_accepted(db, ceremony["id"], p["id"]) == 1

    # Ceremony can continue — status can be updated.
    status_resp = client.patch(
        f"/ceremonies/{ceremony['id']}/status", json={"status": "completed"}
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "completed"


# --------------------------------------------------------------------------- #
# AUDIT API
# --------------------------------------------------------------------------- #
def test_audit_endpoint_lists_events(client: TestClient) -> None:
    ceremony, participant, attempt = _setup(client)
    submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-A"
    )
    submit_contribution_raw(
        client, ceremony["id"], attempt["id"], participant["id"], "data-B"
    )
    response = client.get(f"/ceremonies/{ceremony['id']}/audit")
    assert response.status_code == 200
    events = response.json()
    types = [e["event_type"] for e in events]
    assert "contribution_submitted" in types
    assert "CONTRIBUTION_CONFLICT" in types


def test_audit_endpoint_ceremony_not_found(client: TestClient) -> None:
    response = client.get("/ceremonies/999999/audit")
    assert response.status_code == 404
