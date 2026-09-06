"""Tests for the Ceremony Timeline and "Why rejected?" explanation features.

These tests verify:

1. The audit endpoint returns the correct events for a ceremony (timeline data
   source) and does not leak events from other ceremonies.
2. Timeline events are returned in chronological order (by id).
3. The duplicate/conflict contribution response now contains enough
   information for the "Why rejected?" explanation
   (``original_contribution_id``, ``submitted_contribution_id``,
   ``original_hash``, ``reason``).
4. The explanation correctly distinguishes DUPLICATE vs CONFLICT.
5. The original canonical contribution remains unchanged after a
   duplicate/conflict.
6. Existing duplicate/conflict behavior still works.
7. Existing recovery and final verification behavior still works.
"""

from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from tests.helpers import (
    create_attempt,
    create_ceremony,
    create_participant,
    submit_contribution,
    submit_contribution_raw,
)


def _hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Timeline — audit endpoint data
# --------------------------------------------------------------------------- #
def test_timeline_loads_audit_events_for_correct_ceremony(client: TestClient) -> None:
    """GET /ceremonies/{id}/audit returns only that ceremony's events."""
    c1 = create_ceremony(client, "Ceremony 1")
    c2 = create_ceremony(client, "Ceremony 2")
    create_participant(client, c1["id"], "Alice")
    create_participant(client, c2["id"], "Bob")

    e1 = client.get(f"/ceremonies/{c1['id']}/audit")
    e2 = client.get(f"/ceremonies/{c2['id']}/audit")
    assert e1.status_code == 200
    assert e2.status_code == 200

    # Each ceremony's audit list must only reference its own ceremony id.
    for ev in e1.json():
        assert ev["ceremony_id"] == c1["id"]
    for ev in e2.json():
        assert ev["ceremony_id"] == c2["id"]


def test_timeline_does_not_show_events_from_another_ceremony(client: TestClient) -> None:
    c1 = create_ceremony(client, "Ceremony A")
    c2 = create_ceremony(client, "Ceremony B")
    p1 = create_participant(client, c1["id"], "Alice")
    p2 = create_participant(client, c2["id"], "Bob")
    a1 = create_attempt(client, c1["id"])
    a2 = create_attempt(client, c2["id"])
    submit_contribution_raw(client, c1["id"], a1["id"], p1["id"], "alice-data")
    submit_contribution_raw(client, c2["id"], a2["id"], p2["id"], "bob-data")

    e1 = client.get(f"/ceremonies/{c1['id']}/audit").json()
    e2 = client.get(f"/ceremonies/{c2['id']}/audit").json()

    e1_participants = {ev["participant_id"] for ev in e1 if ev["participant_id"]}
    e2_participants = {ev["participant_id"] for ev in e2 if ev["participant_id"]}

    assert p1["id"] in e1_participants
    assert p2["id"] not in e1_participants
    assert p2["id"] in e2_participants
    assert p1["id"] not in e2_participants


def test_timeline_displays_events_in_correct_order(client: TestClient) -> None:
    """Audit events are ordered by id (chronological)."""
    c = create_ceremony(client, "Order Test")
    p1 = create_participant(client, c["id"], "Alice")
    p2 = create_participant(client, c["id"], "Bob")
    a = create_attempt(client, c["id"])
    submit_contribution_raw(client, c["id"], a["id"], p1["id"], "data-a")
    submit_contribution_raw(client, c["id"], a["id"], p2["id"], "data-b")

    events = client.get(f"/ceremonies/{c['id']}/audit").json()
    ids = [ev["id"] for ev in events]
    assert ids == sorted(ids)
    # First event should be ceremony_created.
    assert events[0]["event_type"] == "ceremony_created"
    # The accepted contribution events should come after participant/attempt
    # creation events.
    types = [ev["event_type"] for ev in events]
    assert types.index("contribution_submitted") > types.index("attempt_created")


# --------------------------------------------------------------------------- #
# "Why rejected?" — duplicate response data
# --------------------------------------------------------------------------- #
def test_duplicate_response_contains_enough_information(client: TestClient) -> None:
    c = create_ceremony(client, "Dup Test")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])

    first = submit_contribution_raw(client, c["id"], a["id"], p["id"], "alice-c1")
    assert first.status_code == 201
    first_body = first.json()

    dup = submit_contribution_raw(client, c["id"], a["id"], p["id"], "alice-c1")
    assert dup.status_code == 200
    body = dup.json()

    assert body["status"] == "duplicate"
    # New optional fields for the "Why rejected?" explanation.
    assert body["original_contribution_id"] == first_body["contribution"]["id"]
    assert body["submitted_contribution_id"] is not None
    assert body["submitted_contribution_id"] != body["original_contribution_id"]
    assert body["original_hash"] == _hash("alice-c1")
    assert body["submitted_hash"] == _hash("alice-c1")
    assert body["original_hash"] == body["submitted_hash"]
    assert body["reason"] is not None
    assert "same" in body["reason"].lower()


def test_conflict_response_contains_enough_information(client: TestClient) -> None:
    c = create_ceremony(client, "Conflict Test")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])

    first = submit_contribution_raw(client, c["id"], a["id"], p["id"], "alice-c1")
    assert first.status_code == 201

    conflict = submit_contribution_raw(client, c["id"], a["id"], p["id"], "alice-c2")
    assert conflict.status_code == 409
    body = conflict.json()

    assert body["status"] == "conflict"
    assert body["original_contribution_id"] == first.json()["contribution"]["id"]
    assert body["submitted_contribution_id"] is not None
    assert body["submitted_contribution_id"] != body["original_contribution_id"]
    assert body["original_hash"] == _hash("alice-c1")
    assert body["submitted_hash"] == _hash("alice-c2")
    assert body["original_hash"] != body["submitted_hash"]
    assert body["reason"] is not None
    assert "different" in body["reason"].lower()


def test_accepted_response_has_null_rejection_fields(client: TestClient) -> None:
    """Accepted submissions must not populate rejection-only fields."""
    c = create_ceremony(client, "Accepted Test")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])
    res = submit_contribution_raw(client, c["id"], a["id"], p["id"], "alice-c1")
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "accepted"
    assert body["original_contribution_id"] is None
    assert body["submitted_contribution_id"] is None
    assert body["original_hash"] is None
    assert body["reason"] is None


# --------------------------------------------------------------------------- #
# Explanation distinguishes DUPLICATE vs CONFLICT
# --------------------------------------------------------------------------- #
def test_explanation_distinguishes_duplicate_vs_conflict(client: TestClient) -> None:
    c = create_ceremony(client, "Explanation Test")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])

    submit_contribution_raw(client, c["id"], a["id"], p["id"], "alice-c1")

    dup = submit_contribution_raw(client, c["id"], a["id"], p["id"], "alice-c1").json()
    conflict = submit_contribution_raw(client, c["id"], a["id"], p["id"], "alice-c2").json()

    # Duplicate reason mentions "same"; conflict reason mentions "different".
    assert "same" in dup["reason"].lower()
    assert "different" in conflict["reason"].lower()
    # Duplicate: hashes match. Conflict: hashes differ.
    assert dup["original_hash"] == dup["submitted_hash"]
    assert conflict["original_hash"] != conflict["submitted_hash"]


# --------------------------------------------------------------------------- #
# Original canonical contribution remains unchanged
# --------------------------------------------------------------------------- #
def test_original_canonical_remains_unchanged_after_duplicate(client: TestClient) -> None:
    c = create_ceremony(client, "Canonical Unchanged Dup")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])

    first = submit_contribution(client, c["id"], a["id"], p["id"], "alice-c1")
    dup = submit_contribution(client, c["id"], a["id"], p["id"], "alice-c1")

    assert dup["contribution"]["id"] == first["contribution"]["id"]
    assert dup["contribution"]["contribution_hash"] == first["contribution"]["contribution_hash"]
    assert dup["contribution"]["status"] == "accepted"


def test_original_canonical_remains_unchanged_after_conflict(client: TestClient) -> None:
    c = create_ceremony(client, "Canonical Unchanged Conflict")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])

    first = submit_contribution(client, c["id"], a["id"], p["id"], "alice-c1")
    conflict = submit_contribution(client, c["id"], a["id"], p["id"], "alice-c2")

    assert conflict["contribution"]["id"] == first["contribution"]["id"]
    assert conflict["contribution"]["contribution_hash"] == first["contribution"]["contribution_hash"]
    assert conflict["contribution"]["status"] == "accepted"


# --------------------------------------------------------------------------- #
# Existing behavior regression checks
# --------------------------------------------------------------------------- #
def test_existing_duplicate_behavior_still_works(client: TestClient) -> None:
    """Duplicate returns HTTP 200 and the original is retained."""
    c = create_ceremony(client, "Regression Dup")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])
    submit_contribution_raw(client, c["id"], a["id"], p["id"], "data-x")
    res = submit_contribution_raw(client, c["id"], a["id"], p["id"], "data-x")
    assert res.status_code == 200
    assert res.json()["status"] == "duplicate"


def test_existing_conflict_behavior_still_works(client: TestClient) -> None:
    """Conflict returns HTTP 409 and the original is retained."""
    c = create_ceremony(client, "Regression Conflict")
    p = create_participant(client, c["id"], "Alice")
    a = create_attempt(client, c["id"])
    submit_contribution_raw(client, c["id"], a["id"], p["id"], "data-x")
    res = submit_contribution_raw(client, c["id"], a["id"], p["id"], "data-y")
    assert res.status_code == 409
    assert res.json()["status"] == "conflict"


def test_existing_recovery_behavior_still_works(client: TestClient) -> None:
    """Recovery start + status still function."""
    c = create_ceremony(client, "Regression Recovery")
    p1 = create_participant(client, c["id"], "Alice")
    p2 = create_participant(client, c["id"], "Bob")
    a = create_attempt(client, c["id"])
    submit_contribution_raw(client, c["id"], a["id"], p1["id"], "alice")

    status = client.get(f"/ceremonies/{c['id']}/recovery/status")
    assert status.status_code == 200
    assert status.json()["ready"] is False

    start = client.post(f"/ceremonies/{c['id']}/recovery/start")
    assert start.status_code == 200
    assert start.json()["ceremony_status"] == "recovering"

    resume = client.post(
        f"/ceremonies/{c['id']}/recovery/resume",
        json={"participant_id": p2["id"], "contribution_data": "bob"},
    )
    assert resume.status_code == 201
    assert resume.json()["submission_status"] == "accepted"

    status2 = client.get(f"/ceremonies/{c['id']}/recovery/status")
    assert status2.json()["ready"] is True


def test_existing_final_verification_behavior_still_works(client: TestClient) -> None:
    """Finalize + verify still function end-to-end."""
    c = create_ceremony(client, "Regression Verification")
    p1 = create_participant(client, c["id"], "Alice")
    p2 = create_participant(client, c["id"], "Bob")
    a = create_attempt(client, c["id"])
    submit_contribution_raw(client, c["id"], a["id"], p1["id"], "alice")
    submit_contribution_raw(client, c["id"], a["id"], p2["id"], "bob")

    finalize = client.post(f"/ceremonies/{c['id']}/finalize")
    assert finalize.status_code == 200
    assert finalize.json()["generated"] is True

    verify = client.post(f"/ceremonies/{c['id']}/verify")
    assert verify.status_code == 200
    assert verify.json()["verified"] is True
    assert verify.json()["verification_status"] == "verified"


def test_timeline_includes_recovery_and_verification_events(client: TestClient) -> None:
    """The audit trail (timeline data source) includes recovery + verification events."""
    c = create_ceremony(client, "Timeline Full")
    p1 = create_participant(client, c["id"], "Alice")
    p2 = create_participant(client, c["id"], "Bob")
    a = create_attempt(client, c["id"])
    submit_contribution_raw(client, c["id"], a["id"], p1["id"], "alice")

    client.post(f"/ceremonies/{c['id']}/recovery/start")
    client.post(
        f"/ceremonies/{c['id']}/recovery/resume",
        json={"participant_id": p2["id"], "contribution_data": "bob"},
    )
    client.post(f"/ceremonies/{c['id']}/finalize")
    client.post(f"/ceremonies/{c['id']}/verify")

    events = client.get(f"/ceremonies/{c['id']}/audit").json()
    types = [ev["event_type"] for ev in events]
    assert "CEREMONY_RECOVERY_STARTED" in types
    assert "PARTICIPANT_RECOVERY_RESUMED" in types
    assert "FINAL_RESULT_GENERATED" in types
    assert "FINAL_RESULT_VERIFIED" in types
