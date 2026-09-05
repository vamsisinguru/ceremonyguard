"""Phase 4 tests — recovery and final verification."""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AuditEvent, Contribution, CeremonyResult
from fastapi.testclient import TestClient

from tests.helpers import (
    create_attempt,
    create_ceremony,
    create_participant,
    submit_contribution,
    submit_contribution_raw,
)


def _get_session(client: TestClient) -> Session:
    return client.app.dependency_overrides[get_db]().__next__()


def _audit_types(db: Session, ceremony_id: int) -> list[str]:
    events = list(
        db.scalars(
            select(AuditEvent).where(AuditEvent.ceremony_id == ceremony_id)
        )
    )
    return [e.event_type for e in events]


def _setup_full_ceremony(client: TestClient, n_participants: int = 3):
    """Create a ceremony with N participants and one attempt."""
    ceremony = create_ceremony(client, "Phase 4 Ceremony")
    participants = []
    for i in range(n_participants):
        p = create_participant(client, ceremony["id"], f"Participant {chr(65 + i)}")
        participants.append(p)
    attempt = create_attempt(client, ceremony["id"])
    return ceremony, participants, attempt


# --------------------------------------------------------------------------- #
# CEREMONY COMPLETION CHECK
# --------------------------------------------------------------------------- #
def test_ceremony_with_all_participants_is_ready(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 3)
    for i, p in enumerate(participants):
        submit_contribution_raw(
            client, ceremony["id"], attempt["id"], p["id"], f"data-{i}"
        )
    resp = client.get(f"/ceremonies/{ceremony['id']}/recovery/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["total_participants"] == 3
    assert body["participants_with_contribution"] == 3
    assert len(body["incomplete_participants"]) == 0


def test_ceremony_with_missing_participant_is_incomplete(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 3)
    # Only first 2 participants submit.
    submit_contribution_raw(client, ceremony["id"], attempt["id"], participants[0]["id"], "A")
    submit_contribution_raw(client, ceremony["id"], attempt["id"], participants[1]["id"], "B")
    resp = client.get(f"/ceremonies/{ceremony['id']}/recovery/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is False
    assert body["participants_with_contribution"] == 2
    assert len(body["incomplete_participants"]) == 1
    assert body["incomplete_participants"][0]["participant_id"] == participants[2]["id"]


# --------------------------------------------------------------------------- #
# RECOVERY
# --------------------------------------------------------------------------- #
def test_existing_accepted_contributions_survive_recovery(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 3)
    # Alice and Bob submit.
    r_a = submit_contribution_raw(client, ceremony["id"], attempt["id"], participants[0]["id"], "A")
    r_b = submit_contribution_raw(client, ceremony["id"], attempt["id"], participants[1]["id"], "B")
    alice_contrib_id = r_a.json()["contribution"]["id"]
    bob_contrib_id = r_b.json()["contribution"]["id"]

    # Start recovery.
    rec = client.post(f"/ceremonies/{ceremony['id']}/recovery/start")
    assert rec.status_code == 200

    # Alice and Bob's contributions still exist and are accepted.
    db = _get_session(client)
    alice_contrib = db.get(Contribution, alice_contrib_id)
    bob_contrib = db.get(Contribution, bob_contrib_id)
    assert alice_contrib.status == "accepted"
    assert bob_contrib.status == "accepted"


def test_missing_participant_can_resume(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 3)
    submit_contribution_raw(client, ceremony["id"], attempt["id"], participants[0]["id"], "A")
    submit_contribution_raw(client, ceremony["id"], attempt["id"], participants[1]["id"], "B")

    # Start recovery.
    rec = client.post(f"/ceremonies/{ceremony['id']}/recovery/start")
    assert rec.status_code == 200

    # Charlie resumes.
    resume = client.post(
        f"/ceremonies/{ceremony['id']}/recovery/resume",
        json={"participant_id": participants[2]["id"], "contribution_data": "C"},
    )
    assert resume.status_code in (200, 201)
    body = resume.json()
    assert body["submission_status"] == "accepted"

    # Now ceremony should be ready.
    status_resp = client.get(f"/ceremonies/{ceremony['id']}/recovery/status")
    assert status_resp.json()["ready"] is True


def test_recovery_does_not_force_existing_participants_to_restart(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 3)
    submit_contribution_raw(client, ceremony["id"], attempt["id"], participants[0]["id"], "A")
    submit_contribution_raw(client, ceremony["id"], attempt["id"], participants[1]["id"], "B")

    rec = client.post(f"/ceremonies/{ceremony['id']}/recovery/start")
    assert rec.status_code == 200

    # Only Charlie needs to resume — Alice and Bob don't need to resubmit.
    resume = client.post(
        f"/ceremonies/{ceremony['id']}/recovery/resume",
        json={"participant_id": participants[2]["id"], "contribution_data": "C"},
    )
    assert resume.status_code in (200, 201)

    # Ceremony is ready without Alice/Bob resubmitting.
    status_resp = client.get(f"/ceremonies/{ceremony['id']}/recovery/status")
    assert status_resp.json()["ready"] is True


def test_recovery_preserves_ceremony_identity(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 2)
    submit_contribution_raw(client, ceremony["id"], attempt["id"], participants[0]["id"], "A")

    rec = client.post(f"/ceremonies/{ceremony['id']}/recovery/start")
    assert rec.status_code == 200
    body = rec.json()
    assert body["ceremony_id"] == ceremony["id"]
    # The ceremony object itself still exists with the same ID.
    cer = client.get(f"/ceremonies/{ceremony['id']}")
    assert cer.json()["id"] == ceremony["id"]


def test_wrong_ceremony_contribution_cannot_be_used_during_recovery(client: TestClient) -> None:
    """A participant from ceremony 2 cannot resume in ceremony 1's recovery."""
    c1 = create_ceremony(client, "Ceremony 1")
    c2 = create_ceremony(client, "Ceremony 2")
    p1 = create_participant(client, c1["id"], "Alice")
    p2 = create_participant(client, c2["id"], "Bob")
    a1 = create_attempt(client, c1["id"])
    submit_contribution_raw(client, c1["id"], a1["id"], p1["id"], "A")

    rec = client.post(f"/ceremonies/{c1['id']}/recovery/start")
    assert rec.status_code == 200

    # Bob (from ceremony 2) tries to resume in ceremony 1.
    resume = client.post(
        f"/ceremonies/{c1['id']}/recovery/resume",
        json={"participant_id": p2["id"], "contribution_data": "B"},
    )
    assert resume.status_code == 400
    assert "ceremony" in resume.json()["detail"].lower()


def test_duplicate_during_recovery_remains_duplicate(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 2)
    submit_contribution_raw(client, ceremony["id"], attempt["id"], participants[0]["id"], "A")
    # Start recovery.
    client.post(f"/ceremonies/{ceremony['id']}/recovery/start")

    # Participant 1 resubmits the same data during recovery → duplicate.
    resume = client.post(
        f"/ceremonies/{ceremony['id']}/recovery/resume",
        json={"participant_id": participants[0]["id"], "contribution_data": "A"},
    )
    assert resume.status_code == 200
    body = resume.json()
    assert body["submission_status"] == "duplicate"


def test_conflict_during_recovery_remains_conflict(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 2)
    submit_contribution_raw(client, ceremony["id"], attempt["id"], participants[0]["id"], "A")
    # Start recovery.
    client.post(f"/ceremonies/{ceremony['id']}/recovery/start")

    # Participant 1 submits different data during recovery → conflict.
    resume = client.post(
        f"/ceremonies/{ceremony['id']}/recovery/resume",
        json={"participant_id": participants[0]["id"], "contribution_data": "DIFFERENT"},
    )
    assert resume.status_code == 409
    body = resume.json()
    assert body["submission_status"] == "conflict"


def test_recovery_start_creates_audit_event(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 2)
    submit_contribution_raw(client, ceremony["id"], attempt["id"], participants[0]["id"], "A")
    client.post(f"/ceremonies/{ceremony['id']}/recovery/start")
    db = _get_session(client)
    types = _audit_types(db, ceremony["id"])
    assert "CEREMONY_RECOVERY_STARTED" in types


def test_recovery_resume_creates_audit_event(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 2)
    submit_contribution_raw(client, ceremony["id"], attempt["id"], participants[0]["id"], "A")
    client.post(f"/ceremonies/{ceremony['id']}/recovery/start")
    client.post(
        f"/ceremonies/{ceremony['id']}/recovery/resume",
        json={"participant_id": participants[1]["id"], "contribution_data": "B"},
    )
    db = _get_session(client)
    types = _audit_types(db, ceremony["id"])
    assert "PARTICIPANT_RECOVERY_RESUMED" in types


def test_recovery_status_ceremony_not_found(client: TestClient) -> None:
    resp = client.get("/ceremonies/999999/recovery/status")
    assert resp.status_code == 404


def test_recovery_start_ceremony_not_found(client: TestClient) -> None:
    resp = client.post("/ceremonies/999999/recovery/start")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# FINAL VERIFICATION
# --------------------------------------------------------------------------- #
def test_final_verification_succeeds_with_all_canonical(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 3)
    for i, p in enumerate(participants):
        submit_contribution_raw(client, ceremony["id"], attempt["id"], p["id"], f"data-{i}")

    # Finalize.
    fin = client.post(f"/ceremonies/{ceremony['id']}/finalize")
    assert fin.status_code == 200
    body = fin.json()
    assert body["generated"] is True
    assert body["verified"] is True
    assert body["verification_status"] == "verified"
    assert body["final_digest"]
    assert body["contribution_digest"]
    assert body["participant_count"] == 3
    assert len(body["canonical_contributions"]) == 3

    # Verify again.
    ver = client.post(f"/ceremonies/{ceremony['id']}/verify")
    assert ver.status_code == 200
    assert ver.json()["verified"] is True


def test_final_verification_fails_when_contribution_modified(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 3)
    for i, p in enumerate(participants):
        submit_contribution_raw(client, ceremony["id"], attempt["id"], p["id"], f"data-{i}")

    client.post(f"/ceremonies/{ceremony['id']}/finalize")

    # Tamper with a canonical contribution directly in the DB.
    db = _get_session(client)
    contrib = db.scalar(
        select(Contribution).where(
            Contribution.ceremony_id == ceremony["id"],
            Contribution.participant_id == participants[0]["id"],
            Contribution.status == "accepted",
        )
    )
    contrib.contribution_hash = hashlib.sha256(b"tampered").hexdigest()
    contrib.contribution_data = "tampered"
    db.commit()

    ver = client.post(f"/ceremonies/{ceremony['id']}/verify")
    assert ver.status_code == 200
    body = ver.json()
    assert body["verified"] is False
    assert body["verification_status"] == "verification_failed"


def test_final_verification_fails_when_contribution_removed(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 3)
    for i, p in enumerate(participants):
        submit_contribution_raw(client, ceremony["id"], attempt["id"], p["id"], f"data-{i}")

    client.post(f"/ceremonies/{ceremony['id']}/finalize")

    # Remove a canonical contribution (change its status to conflict so the
    # partial unique index doesn't block the update).
    db = _get_session(client)
    contrib = db.scalar(
        select(Contribution).where(
            Contribution.ceremony_id == ceremony["id"],
            Contribution.participant_id == participants[0]["id"],
            Contribution.status == "accepted",
        )
    )
    contrib.status = "conflict"
    db.commit()

    ver = client.post(f"/ceremonies/{ceremony['id']}/verify")
    assert ver.status_code == 200
    body = ver.json()
    assert body["verified"] is False
    assert body["verification_status"] == "verification_failed"


def test_final_result_traceable_to_one_canonical_per_participant(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 3)
    for i, p in enumerate(participants):
        submit_contribution_raw(client, ceremony["id"], attempt["id"], p["id"], f"data-{i}")

    fin = client.post(f"/ceremonies/{ceremony['id']}/finalize")
    body = fin.json()
    contribs = body["canonical_contributions"]
    # Exactly one per participant.
    participant_ids = [c["participant_id"] for c in contribs]
    assert len(participant_ids) == 3
    assert len(set(participant_ids)) == 3
    # Each has a contribution ID, hash, and attempt ID.
    for c in contribs:
        assert c["contribution_id"] > 0
        assert c["contribution_hash"]
        assert c["attempt_id"] > 0
        assert c["participant_name"]


def test_finalize_not_ready(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 3)
    # Only 1 of 3 participants submits.
    submit_contribution_raw(client, ceremony["id"], attempt["id"], participants[0]["id"], "A")

    fin = client.post(f"/ceremonies/{ceremony['id']}/finalize")
    assert fin.status_code == 400
    assert "not ready" in fin.json()["detail"].lower()


def test_get_verification_not_generated(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 3)
    for i, p in enumerate(participants):
        submit_contribution_raw(client, ceremony["id"], attempt["id"], p["id"], f"data-{i}")

    ver = client.get(f"/ceremonies/{ceremony['id']}/verification")
    assert ver.status_code == 200
    body = ver.json()
    assert body["generated"] is False
    assert body["verification_status"] == "not_generated"
    assert body["ready"] is True


def test_get_verification_not_ready(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 3)
    submit_contribution_raw(client, ceremony["id"], attempt["id"], participants[0]["id"], "A")

    ver = client.get(f"/ceremonies/{ceremony['id']}/verification")
    assert ver.status_code == 200
    body = ver.json()
    assert body["generated"] is False
    assert body["verification_status"] == "not_ready"
    assert body["ready"] is False


def test_verify_without_finalize(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 3)
    for i, p in enumerate(participants):
        submit_contribution_raw(client, ceremony["id"], attempt["id"], p["id"], f"data-{i}")

    ver = client.post(f"/ceremonies/{ceremony['id']}/verify")
    assert ver.status_code == 400
    assert "not been generated" in ver.json()["detail"].lower()


def test_final_verification_audit_events(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 3)
    for i, p in enumerate(participants):
        submit_contribution_raw(client, ceremony["id"], attempt["id"], p["id"], f"data-{i}")

    client.post(f"/ceremonies/{ceremony['id']}/finalize")
    db = _get_session(client)
    types = _audit_types(db, ceremony["id"])
    assert "FINAL_RESULT_GENERATED" in types
    assert "FINAL_RESULT_VERIFIED" in types


def test_verification_failed_audit_event(client: TestClient) -> None:
    ceremony, participants, attempt = _setup_full_ceremony(client, 3)
    for i, p in enumerate(participants):
        submit_contribution_raw(client, ceremony["id"], attempt["id"], p["id"], f"data-{i}")

    client.post(f"/ceremonies/{ceremony['id']}/finalize")

    # Tamper.
    db = _get_session(client)
    contrib = db.scalar(
        select(Contribution).where(
            Contribution.ceremony_id == ceremony["id"],
            Contribution.participant_id == participants[0]["id"],
            Contribution.status == "accepted",
        )
    )
    contrib.contribution_hash = hashlib.sha256(b"tampered").hexdigest()
    db.commit()

    client.post(f"/ceremonies/{ceremony['id']}/verify")
    db2 = _get_session(client)
    types = _audit_types(db2, ceremony["id"])
    assert "FINAL_RESULT_VERIFICATION_FAILED" in types


def test_verification_ceremony_not_found(client: TestClient) -> None:
    assert client.get("/ceremonies/999999/verification").status_code == 404
    assert client.post("/ceremonies/999999/finalize").status_code == 404
    assert client.post("/ceremonies/999999/verify").status_code == 404


# --------------------------------------------------------------------------- #
# FULL RECOVERY + VERIFICATION DEMO
# --------------------------------------------------------------------------- #
def test_full_recovery_and_verification_demo(client: TestClient) -> None:
    """Full demo: 3 participants, 1 fails, recovery, then final verification."""
    ceremony = create_ceremony(client, "Demo Recovery Ceremony")
    pa = create_participant(client, ceremony["id"], "Alice")
    pb = create_participant(client, ceremony["id"], "Bob")
    pc = create_participant(client, ceremony["id"], "Charlie")
    attempt = create_attempt(client, ceremony["id"])

    # Alice and Bob submit; Charlie fails (network failure).
    submit_contribution_raw(client, ceremony["id"], attempt["id"], pa["id"], "A-share")
    submit_contribution_raw(client, ceremony["id"], attempt["id"], pb["id"], "B-share")

    # Ceremony is not ready.
    status = client.get(f"/ceremonies/{ceremony['id']}/recovery/status").json()
    assert status["ready"] is False
    assert len(status["incomplete_participants"]) == 1

    # Start recovery.
    rec = client.post(f"/ceremonies/{ceremony['id']}/recovery/start")
    assert rec.status_code == 200
    assert rec.json()["ceremony_status"] == "recovering"

    # Charlie resumes.
    resume = client.post(
        f"/ceremonies/{ceremony['id']}/recovery/resume",
        json={"participant_id": pc["id"], "contribution_data": "C-share"},
    )
    assert resume.status_code in (200, 201)
    assert resume.json()["submission_status"] == "accepted"

    # Ceremony is now ready.
    status = client.get(f"/ceremonies/{ceremony['id']}/recovery/status").json()
    assert status["ready"] is True

    # Finalize and verify.
    fin = client.post(f"/ceremonies/{ceremony['id']}/finalize")
    assert fin.status_code == 200
    assert fin.json()["verified"] is True
    assert fin.json()["participant_count"] == 3

    # Audit trail has recovery and verification events.
    db = _get_session(client)
    types = _audit_types(db, ceremony["id"])
    assert "CEREMONY_RECOVERY_STARTED" in types
    assert "PARTICIPANT_RECOVERY_RESUMED" in types
    assert "FINAL_RESULT_GENERATED" in types
    assert "FINAL_RESULT_VERIFIED" in types
