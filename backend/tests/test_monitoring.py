"""Tests for Smart Ceremony Monitoring & Automatic Recovery.

Covers:

1. Idempotent submission with submission_key.
2. Submission status lookup endpoint.
3. Retry after simulated lost response finds existing accepted contribution.
4. Retry does not create another canonical contribution.
5. First request never reached server and retry succeeds.
6. Existing duplicate/conflict behavior remains correct with submission_key.
7. Cross-ceremony recovery is rejected.
8. Recovery audit events are created.
9. Manual-action state is generated when recovery is unsafe.
10. Incomplete ceremony cannot become VERIFIED.
11. Existing verification still passes after safe recovery.
12. Ceremony monitor endpoint returns correct statuses.
"""

from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from tests.helpers import (
    create_attempt,
    create_ceremony,
    create_participant,
    submit_contribution_raw,
)


def _hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def submit_with_key(
    client: TestClient,
    ceremony_id: int,
    attempt_id: int,
    participant_id: int,
    data: str,
    submission_key: str,
):
    """Submit a contribution with a submission_key and return the raw response."""
    return client.post(
        f"/ceremonies/{ceremony_id}/attempts/{attempt_id}/contributions",
        json={
            "participant_id": participant_id,
            "contribution_data": data,
            "submission_key": submission_key,
        },
    )


# --------------------------------------------------------------------------- #
# 1. Idempotent submission with submission_key
# --------------------------------------------------------------------------- #
def test_first_submission_with_key_succeeds(client: TestClient) -> None:
    c = create_ceremony(client, "Idempotent Test")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])

    res = submit_with_key(client, c["id"], a["id"], p["id"], "alice-data", "key-1")
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "accepted"
    assert body["contribution"]["id"] is not None


def test_retry_with_same_key_returns_existing_result(client: TestClient) -> None:
    """Retrying with the same submission_key returns the original result."""
    c = create_ceremony(client, "Retry Same Key")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])

    first = submit_with_key(client, c["id"], a["id"], p["id"], "alice-data", "key-1")
    assert first.status_code == 201
    first_id = first.json()["contribution"]["id"]

    # Retry with the same key — should return the same contribution.
    retry = submit_with_key(client, c["id"], a["id"], p["id"], "alice-data", "key-1")
    assert retry.status_code == 201
    body = retry.json()
    assert body["status"] == "accepted"
    assert body["contribution"]["id"] == first_id


def test_retry_does_not_create_another_canonical(client: TestClient) -> None:
    """Retrying with the same key must not create a second canonical contribution."""
    c = create_ceremony(client, "No Double Canonical")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])

    submit_with_key(client, c["id"], a["id"], p["id"], "alice-data", "key-1")
    submit_with_key(client, c["id"], a["id"], p["id"], "alice-data", "key-1")
    submit_with_key(client, c["id"], a["id"], p["id"], "alice-data", "key-1")

    # List all contributions — there should be exactly one accepted.
    all_contribs = client.get(f"/ceremonies/{c['id']}/contributions").json()
    accepted = [x for x in all_contribs if x["status"] == "accepted"]
    assert len(accepted) == 1


# --------------------------------------------------------------------------- #
# 2. Submission status lookup endpoint
# --------------------------------------------------------------------------- #
def test_submission_status_accepted(client: TestClient) -> None:
    c = create_ceremony(client, "Status Accepted")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])
    submit_with_key(client, c["id"], a["id"], p["id"], "alice-data", "key-1")

    res = client.get(f"/ceremonies/{c['id']}/submissions/key-1/status")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ACCEPTED"
    assert body["contribution_id"] is not None
    assert body["participant_id"] == p["id"]


def test_submission_status_not_found(client: TestClient) -> None:
    c = create_ceremony(client, "Status Not Found")
    res = client.get(f"/ceremonies/{c['id']}/submissions/nonexistent-key/status")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "NOT_FOUND"


def test_submission_status_ceremony_not_found(client: TestClient) -> None:
    res = client.get("/ceremonies/9999/submissions/key-1/status")
    assert res.status_code == 404


# --------------------------------------------------------------------------- #
# 3 & 4. Retry after simulated lost response
# --------------------------------------------------------------------------- #
def test_retry_finds_existing_accepted_contribution(client: TestClient) -> None:
    """Simulate: C submits, server saves, response lost. C retries → finds existing."""
    c = create_ceremony(client, "Lost Response")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])

    # First submission succeeds (server received it).
    first = submit_with_key(client, c["id"], a["id"], p["id"], "alice-data", "key-1")
    assert first.status_code == 201
    first_id = first.json()["contribution"]["id"]

    # Client didn't receive the response and retries with the same key.
    retry = submit_with_key(client, c["id"], a["id"], p["id"], "alice-data", "key-1")
    assert retry.status_code == 201
    assert retry.json()["contribution"]["id"] == first_id

    # Only one canonical contribution exists.
    all_c = client.get(f"/ceremonies/{c['id']}/contributions").json()
    accepted = [x for x in all_c if x["status"] == "accepted"]
    assert len(accepted) == 1


# --------------------------------------------------------------------------- #
# 5. First request never reached server and retry succeeds
# --------------------------------------------------------------------------- #
def test_first_request_never_reached_retry_succeeds(client: TestClient) -> None:
    """Simulate: C submits with key, request lost. C retries with same key → accepted."""
    c = create_ceremony(client, "Never Reached")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])

    # Check status — NOT_FOUND (the submission never reached the server).
    status1 = client.get(f"/ceremonies/{c['id']}/submissions/key-1/status")
    assert status1.json()["status"] == "NOT_FOUND"

    # Retry with the same key — this time it reaches the server.
    retry = submit_with_key(client, c["id"], a["id"], p["id"], "alice-data", "key-1")
    assert retry.status_code == 201
    assert retry.json()["status"] == "accepted"

    # Now status should be ACCEPTED.
    status2 = client.get(f"/ceremonies/{c['id']}/submissions/key-1/status")
    assert status2.json()["status"] == "ACCEPTED"


# --------------------------------------------------------------------------- #
# 6. Existing duplicate/conflict behavior with submission_key
# --------------------------------------------------------------------------- #
def test_duplicate_behavior_with_key(client: TestClient) -> None:
    """Duplicate behavior preserved when submission_key is used."""
    c = create_ceremony(client, "Dup With Key")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])

    # First submission with key-1.
    first = submit_with_key(client, c["id"], a["id"], p["id"], "alice-data", "key-1")
    assert first.status_code == 201

    # Second submission with a DIFFERENT key but same data → duplicate.
    second = submit_with_key(client, c["id"], a["id"], p["id"], "alice-data", "key-2")
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"


def test_conflict_behavior_with_key(client: TestClient) -> None:
    """Conflict behavior preserved when submission_key is used."""
    c = create_ceremony(client, "Conflict With Key")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])

    first = submit_with_key(client, c["id"], a["id"], p["id"], "alice-data", "key-1")
    assert first.status_code == 201

    # Different data with a different key → conflict.
    second = submit_with_key(client, c["id"], a["id"], p["id"], "alice-data-2", "key-2")
    assert second.status_code == 409
    assert second.json()["status"] == "conflict"


def test_submission_without_key_still_works(client: TestClient) -> None:
    """Submissions without a submission_key continue to work as before."""
    c = create_ceremony(client, "No Key")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])
    res = submit_contribution_raw(client, c["id"], a["id"], p["id"], "alice-data")
    assert res.status_code == 201
    assert res.json()["status"] == "accepted"


# --------------------------------------------------------------------------- #
# 7. Cross-ceremony recovery is rejected
# --------------------------------------------------------------------------- #
def test_cross_ceremony_recovery_report_rejected(client: TestClient) -> None:
    """Recovery report for a participant from a different ceremony is rejected."""
    c1 = create_ceremony(client, "Ceremony 1")
    c2 = create_ceremony(client, "Ceremony 2")
    p1 = create_participant(client, c1["id"], "Alice")

    res = client.post(
        f"/ceremonies/{c2['id']}/recovery/report",
        json={"participant_id": p1["id"]},
    )
    assert res.status_code == 400


def test_cross_ceremony_submission_key_isolated(client: TestClient) -> None:
    """The same submission_key in different ceremonies is independent."""
    c1 = create_ceremony(client, "C1")
    c2 = create_ceremony(client, "C2")
    p1 = create_participant(client, c1["id"], "Alice")
    p2 = create_participant(client, c2["id"], "Bob")
    a1 = create_attempt(client, c1["id"])
    a2 = create_attempt(client, c2["id"])

    submit_with_key(client, c1["id"], a1["id"], p1["id"], "data-1", "shared-key")
    submit_with_key(client, c2["id"], a2["id"], p2["id"], "data-2", "shared-key")

    s1 = client.get(f"/ceremonies/{c1['id']}/submissions/shared-key/status")
    s2 = client.get(f"/ceremonies/{c2['id']}/submissions/shared-key/status")
    assert s1.json()["status"] == "ACCEPTED"
    assert s2.json()["status"] == "ACCEPTED"
    assert s1.json()["contribution_id"] != s2.json()["contribution_id"]


# --------------------------------------------------------------------------- #
# 8. Recovery audit events are created
# --------------------------------------------------------------------------- #
def test_recovery_report_creates_audit_events(client: TestClient) -> None:
    """Generating a recovery report creates SUBMISSION_RECOVERY_STARTED + related events."""
    c = create_ceremony(client, "Audit Events")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])
    submit_with_key(client, c["id"], a["id"], p["id"], "alice-data", "key-1")

    # Generate a recovery report — should find the existing contribution.
    client.post(
        f"/ceremonies/{c['id']}/recovery/report",
        json={"participant_id": p["id"], "submission_key": "key-1"},
    )

    events = client.get(f"/ceremonies/{c['id']}/audit").json()
    event_types = [e["event_type"] for e in events]
    assert "SUBMISSION_RECOVERY_STARTED" in event_types
    assert "SUBMISSION_STATUS_CHECKED" in event_types
    assert "SUBMISSION_ALREADY_ACCEPTED" in event_types


def test_retry_accepted_creates_audit_event(client: TestClient) -> None:
    """A successful safe retry creates a SUBMISSION_RETRY_ACCEPTED event."""
    c = create_ceremony(client, "Retry Audit")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])

    # No prior submission — recovery report with contribution_data triggers retry.
    client.post(
        f"/ceremonies/{c['id']}/recovery/report",
        json={
            "participant_id": p["id"],
            "submission_key": "key-1",
            "contribution_data": "alice-data",
        },
    )

    events = client.get(f"/ceremonies/{c['id']}/audit").json()
    event_types = [e["event_type"] for e in events]
    assert "SUBMISSION_RECOVERY_STARTED" in event_types
    assert "SUBMISSION_RETRY_ACCEPTED" in event_types


# --------------------------------------------------------------------------- #
# 9. Manual-action state when recovery is unsafe
# --------------------------------------------------------------------------- #
def test_manual_action_when_no_data_and_no_key(client: TestClient) -> None:
    """Recovery report without submission_key or contribution_data → manual action."""
    c = create_ceremony(client, "Manual Action")
    p = create_participant(client, c["id"], "Alice")

    res = client.post(
        f"/ceremonies/{c['id']}/recovery/report",
        json={"participant_id": p["id"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["recovery_status"] == "not_safe"
    assert len(body["manual_steps"]) > 0

    events = client.get(f"/ceremonies/{c['id']}/audit").json()
    event_types = [e["event_type"] for e in events]
    assert "SUBMISSION_RECOVERY_FAILED" in event_types
    assert "MANUAL_ACTION_REQUIRED" in event_types


def test_recovery_report_conflict_is_unrecoverable(client: TestClient) -> None:
    """A conflict during retry produces an unrecoverable report."""
    c = create_ceremony(client, "Conflict Unrecoverable")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])

    # First accepted contribution.
    submit_with_key(client, c["id"], a["id"], p["id"], "alice-data", "key-1")

    # Recovery report with DIFFERENT data and a new key → conflict.
    res = client.post(
        f"/ceremonies/{c['id']}/recovery/report",
        json={
            "participant_id": p["id"],
            "submission_key": "key-2",
            "contribution_data": "alice-different",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["recovery_status"] == "not_safe"
    assert "conflict" in body["issue"].lower()


# --------------------------------------------------------------------------- #
# 10. Incomplete ceremony cannot become VERIFIED
# --------------------------------------------------------------------------- #
def test_incomplete_ceremony_cannot_finalize(client: TestClient) -> None:
    """An incomplete ceremony cannot be finalized."""
    c = create_ceremony(client, "Incomplete")
    p1 = create_participant(client, c["id"], "Alice")
    p2 = create_participant(client, c["id"], "Bob")
    a = create_attempt(client, c["id"])
    submit_with_key(client, c["id"], a["id"], p1["id"], "alice-data", "key-1")
    # Bob has not submitted.

    res = client.post(f"/ceremonies/{c['id']}/finalize")
    assert res.status_code == 400


def test_monitor_shows_incomplete(client: TestClient) -> None:
    """Monitor shows 'incomplete' when not all participants have submitted."""
    c = create_ceremony(client, "Monitor Incomplete")
    p1 = create_participant(client, c["id"], "Alice")
    p2 = create_participant(client, c["id"], "Bob")
    a = create_attempt(client, c["id"])
    submit_with_key(client, c["id"], a["id"], p1["id"], "alice-data", "key-1")

    res = client.get(f"/ceremonies/{c['id']}/monitor")
    assert res.status_code == 200
    body = res.json()
    assert body["monitor_status"] == "incomplete"
    assert body["incomplete_count"] == 1
    assert body["total_participants"] == 2


# --------------------------------------------------------------------------- #
# 11. Existing verification still passes after safe recovery
# --------------------------------------------------------------------------- #
def test_verification_passes_after_safe_recovery(client: TestClient) -> None:
    """Full flow: submit, recover, finalize, verify — all succeeds."""
    c = create_ceremony(client, "Full Recovery Flow")
    p1 = create_participant(client, c["id"], "Alice")
    p2 = create_participant(client, c["id"], "Bob")
    a = create_attempt(client, c["id"])

    # Alice submits successfully.
    submit_with_key(client, c["id"], a["id"], p1["id"], "alice-data", "key-alice")

    # Bob's submission "lost" — recovery report with key + data triggers safe retry.
    report = client.post(
        f"/ceremonies/{c['id']}/recovery/report",
        json={
            "participant_id": p2["id"],
            "submission_key": "key-bob",
            "contribution_data": "bob-data",
        },
    )
    assert report.status_code == 200
    assert report.json()["recovery_status"] == "recovered"

    # Now finalize and verify.
    finalize = client.post(f"/ceremonies/{c['id']}/finalize")
    assert finalize.status_code == 200
    assert finalize.json()["generated"] is True

    verify = client.post(f"/ceremonies/{c['id']}/verify")
    assert verify.status_code == 200
    assert verify.json()["verified"] is True


def test_recovery_finds_existing_then_verification_passes(client: TestClient) -> None:
    """Recovery finds existing contribution, then verification passes."""
    c = create_ceremony(client, "Recover Existing")
    p1 = create_participant(client, c["id"], "Alice")
    p2 = create_participant(client, c["id"], "Bob")
    a = create_attempt(client, c["id"])

    # Both submit successfully.
    submit_with_key(client, c["id"], a["id"], p1["id"], "alice-data", "key-alice")
    submit_with_key(client, c["id"], a["id"], p2["id"], "bob-data", "key-bob")

    # Alice's response was "lost" — recovery report finds existing contribution.
    report = client.post(
        f"/ceremonies/{c['id']}/recovery/report",
        json={"participant_id": p1["id"], "submission_key": "key-alice"},
    )
    assert report.status_code == 200
    assert report.json()["recovery_status"] == "recovered"
    assert report.json()["duplicate_created"] is False

    # Finalize and verify.
    finalize = client.post(f"/ceremonies/{c['id']}/finalize")
    assert finalize.json()["generated"] is True
    verify = client.post(f"/ceremonies/{c['id']}/verify")
    assert verify.json()["verified"] is True


# --------------------------------------------------------------------------- #
# 12. Ceremony monitor endpoint
# --------------------------------------------------------------------------- #
def test_monitor_healthy_when_all_submitted(client: TestClient) -> None:
    c = create_ceremony(client, "Monitor Healthy")
    p1 = create_participant(client, c["id"], "Alice")
    p2 = create_participant(client, c["id"], "Bob")
    a = create_attempt(client, c["id"])
    submit_with_key(client, c["id"], a["id"], p1["id"], "alice-data", "key-1")
    submit_with_key(client, c["id"], a["id"], p2["id"], "bob-data", "key-2")

    res = client.get(f"/ceremonies/{c['id']}/monitor")
    assert res.status_code == 200
    body = res.json()
    assert body["monitor_status"] == "healthy"
    assert body["incomplete_count"] == 0
    assert body["participants_with_contribution"] == 2


def test_monitor_not_ready_when_no_participants(client: TestClient) -> None:
    c = create_ceremony(client, "Monitor Empty")
    res = client.get(f"/ceremonies/{c['id']}/monitor")
    assert res.status_code == 200
    body = res.json()
    assert body["monitor_status"] == "not_ready"
    assert body["total_participants"] == 0


def test_monitor_ceremony_not_found(client: TestClient) -> None:
    res = client.get("/ceremonies/9999/monitor")
    assert res.status_code == 404


def test_monitor_shows_conflict_requires_attention(client: TestClient) -> None:
    """Monitor shows conflict_requires_attention when conflicts + missing exist."""
    c = create_ceremony(client, "Monitor Conflict")
    p1 = create_participant(client, c["id"], "Alice")
    p2 = create_participant(client, c["id"], "Bob")
    a = create_attempt(client, c["id"])

    # Alice submits, then submits conflicting data.
    submit_with_key(client, c["id"], a["id"], p1["id"], "alice-data", "key-1")
    submit_with_key(client, c["id"], a["id"], p1["id"], "alice-diff", "key-2")
    # Bob has not submitted.

    res = client.get(f"/ceremonies/{c['id']}/monitor")
    body = res.json()
    # Bob is missing and there's a conflict record for Alice.
    assert body["conflict_count"] >= 1
    assert body["incomplete_count"] == 1


def test_monitor_shows_verified(client: TestClient) -> None:
    """Monitor shows healthy + verified after finalization + verification."""
    c = create_ceremony(client, "Monitor Verified")
    p1 = create_participant(client, c["id"], "Alice")
    p2 = create_participant(client, c["id"], "Bob")
    a = create_attempt(client, c["id"])
    submit_with_key(client, c["id"], a["id"], p1["id"], "alice-data", "key-1")
    submit_with_key(client, c["id"], a["id"], p2["id"], "bob-data", "key-2")

    client.post(f"/ceremonies/{c['id']}/finalize")
    client.post(f"/ceremonies/{c['id']}/verify")

    res = client.get(f"/ceremonies/{c['id']}/monitor")
    body = res.json()
    assert body["has_final_result"] is True
    assert body["verified"] is True
    assert body["monitor_status"] == "healthy"


def test_monitor_shows_verification_failed(client: TestClient) -> None:
    """Monitor shows verification_failed when the canonical set changes."""
    c = create_ceremony(client, "Monitor Verif Failed")
    p1 = create_participant(client, c["id"], "Alice")
    p2 = create_participant(client, c["id"], "Bob")
    a = create_attempt(client, c["id"])
    submit_with_key(client, c["id"], a["id"], p1["id"], "alice-data", "key-1")
    submit_with_key(client, c["id"], a["id"], p2["id"], "bob-data", "key-2")

    client.post(f"/ceremonies/{c['id']}/finalize")
    client.post(f"/ceremonies/{c['id']}/verify")

    # Tamper: submit a conflicting contribution to change the canonical set
    # is not possible (conflict is rejected). Instead, use the test client's
    # DB session to delete a canonical contribution directly.
    from app.core.database import get_db
    from app.main import app
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.core import database as db_module

    # Use the same engine that the test client is using (db_module.engine
    # is patched in conftest.py to point at the in-memory test DB).
    TestSessionLocal = sessionmaker(
        bind=db_module.engine, autocommit=False, autoflush=False, future=True
    )
    db = TestSessionLocal()
    try:
        # SQLite doesn't support LIMIT in DELETE; use a subquery.
        db.execute(
            text(
                "DELETE FROM contributions WHERE id IN ("
                "SELECT id FROM contributions WHERE ceremony_id = :cid "
                "AND status = 'accepted' LIMIT 1)"
            ),
            {"cid": c["id"]},
        )
        db.commit()
    finally:
        db.close()

    res = client.get(f"/ceremonies/{c['id']}/monitor")
    body = res.json()
    assert body["monitor_status"] == "verification_failed"


# --------------------------------------------------------------------------- #
# Recovery report — additional cases
# --------------------------------------------------------------------------- #
def test_recovery_report_ceremony_not_found(client: TestClient) -> None:
    res = client.post(
        "/ceremonies/9999/recovery/report",
        json={"participant_id": 1},
    )
    assert res.status_code == 404


def test_recovery_report_participant_not_found(client: TestClient) -> None:
    c = create_ceremony(client, "Report No Participant")
    res = client.post(
        f"/ceremonies/{c['id']}/recovery/report",
        json={"participant_id": 9999},
    )
    assert res.status_code == 404


def test_recovery_report_no_canonical_no_data_is_unrecoverable(client: TestClient) -> None:
    """No canonical, no submission_key, no contribution_data → manual action."""
    c = create_ceremony(client, "Report Unrecoverable")
    p = create_participant(client, c["id"], "Alice")

    res = client.post(
        f"/ceremonies/{c['id']}/recovery/report",
        json={"participant_id": p["id"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["recovery_status"] == "not_safe"
    assert "Manual" in body["message"] or "manual" in body["message"].lower() or "INCOMPLETE" in body["message"]


def test_recovery_report_with_canonical_no_key_is_recovered(client: TestClient) -> None:
    """Canonical exists but no submission_key → report confirms it."""
    c = create_ceremony(client, "Report Canonical No Key")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])
    submit_contribution_raw(client, c["id"], a["id"], p["id"], "alice-data")

    res = client.post(
        f"/ceremonies/{c['id']}/recovery/report",
        json={"participant_id": p["id"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["recovery_status"] == "recovered"
    assert body["contribution_id"] is not None


# --------------------------------------------------------------------------- #
# Existing behavior regression
# --------------------------------------------------------------------------- #
def test_existing_submission_without_key_unchanged(client: TestClient) -> None:
    """Submissions without submission_key behave exactly as before."""
    c = create_ceremony(client, "Regression No Key")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])

    first = submit_contribution_raw(client, c["id"], a["id"], p["id"], "data-x")
    assert first.status_code == 201

    dup = submit_contribution_raw(client, c["id"], a["id"], p["id"], "data-x")
    assert dup.status_code == 200
    assert dup.json()["status"] == "duplicate"

    conflict = submit_contribution_raw(client, c["id"], a["id"], p["id"], "data-y")
    assert conflict.status_code == 409
    assert conflict.json()["status"] == "conflict"


def test_existing_recovery_still_works(client: TestClient) -> None:
    """Phase 4 recovery still works alongside the new monitoring feature."""
    c = create_ceremony(client, "Regression Phase 4 Recovery")
    p1 = create_participant(client, c["id"], "Alice")
    p2 = create_participant(client, c["id"], "Bob")
    a = create_attempt(client, c["id"])
    submit_contribution_raw(client, c["id"], a["id"], p1["id"], "alice")

    start = client.post(f"/ceremonies/{c['id']}/recovery/start")
    assert start.status_code == 200

    resume = client.post(
        f"/ceremonies/{c['id']}/recovery/resume",
        json={"participant_id": p2["id"], "contribution_data": "bob"},
    )
    assert resume.status_code == 201

    finalize = client.post(f"/ceremonies/{c['id']}/finalize")
    assert finalize.json()["generated"] is True

    verify = client.post(f"/ceremonies/{c['id']}/verify")
    assert verify.json()["verified"] is True
