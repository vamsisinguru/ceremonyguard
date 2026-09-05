"""Tests for the Contribution REST API."""

from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

from tests.helpers import (
    create_attempt,
    create_ceremony,
    create_participant,
    submit_contribution,
)


def _setup_ceremony_with_participant_and_attempt(client: TestClient):
    ceremony = create_ceremony(client, "Contribution Ceremony")
    participant = create_participant(client, ceremony["id"], "Alice")
    attempt = create_attempt(client, ceremony["id"])
    return ceremony, participant, attempt


def test_submit_contribution(client: TestClient) -> None:
    ceremony, participant, attempt = _setup_ceremony_with_participant_and_attempt(client)
    response = client.post(
        f"/ceremonies/{ceremony['id']}/attempts/{attempt['id']}/contributions",
        json={"participant_id": participant["id"], "contribution_data": "hello"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "accepted"
    contrib = body["contribution"]
    assert contrib["id"] > 0
    assert contrib["ceremony_id"] == ceremony["id"]
    assert contrib["attempt_id"] == attempt["id"]
    assert contrib["participant_id"] == participant["id"]
    assert contrib["contribution_data"] == "hello"
    assert contrib["status"] == "accepted"
    assert contrib["created_at"]


def test_contribution_sha256_hash_is_correct(client: TestClient) -> None:
    ceremony, participant, attempt = _setup_ceremony_with_participant_and_attempt(client)
    body = submit_contribution(
        client, ceremony["id"], attempt["id"], participant["id"], "hello"
    )
    expected = hashlib.sha256(b"hello").hexdigest()
    assert body["submitted_hash"] == expected
    assert body["contribution"]["contribution_hash"] == expected
    assert len(body["submitted_hash"]) == 64


def test_contribution_hash_is_deterministic(client: TestClient) -> None:
    """Same data produces the same hash; second submission is a duplicate."""
    ceremony, participant, attempt = _setup_ceremony_with_participant_and_attempt(client)
    b1 = submit_contribution(
        client, ceremony["id"], attempt["id"], participant["id"], "same-data"
    )
    b2 = submit_contribution(
        client, ceremony["id"], attempt["id"], participant["id"], "same-data"
    )
    # Both submissions have the same hash (b2 is a duplicate of b1).
    assert b1["submitted_hash"] == b2["submitted_hash"]
    # The canonical contribution hash matches.
    assert b1["contribution"]["contribution_hash"] == b2["contribution"]["contribution_hash"]


def test_get_contribution(client: TestClient) -> None:
    ceremony, participant, attempt = _setup_ceremony_with_participant_and_attempt(client)
    created = submit_contribution(
        client, ceremony["id"], attempt["id"], participant["id"], "payload"
    )
    contribution_id = created["contribution"]["id"]
    response = client.get(f"/contributions/{contribution_id}")
    assert response.status_code == 200
    assert response.json() == created["contribution"]


def test_get_contribution_not_found(client: TestClient) -> None:
    response = client.get("/contributions/999999")
    assert response.status_code == 404


def test_list_contributions(client: TestClient) -> None:
    ceremony, participant, attempt = _setup_ceremony_with_participant_and_attempt(client)
    submit_contribution(client, ceremony["id"], attempt["id"], participant["id"], "a")
    submit_contribution(client, ceremony["id"], attempt["id"], participant["id"], "b")
    response = client.get(
        f"/ceremonies/{ceremony['id']}/attempts/{attempt['id']}/contributions"
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert {c["contribution_data"] for c in body} == {"a", "b"}


def test_submit_contribution_ceremony_not_found(client: TestClient) -> None:
    ceremony, participant, attempt = _setup_ceremony_with_participant_and_attempt(client)
    response = client.post(
        f"/ceremonies/999999/attempts/{attempt['id']}/contributions",
        json={"participant_id": participant["id"], "contribution_data": "x"},
    )
    assert response.status_code == 404


def test_submit_contribution_attempt_not_found(client: TestClient) -> None:
    ceremony, participant, attempt = _setup_ceremony_with_participant_and_attempt(client)
    response = client.post(
        f"/ceremonies/{ceremony['id']}/attempts/999999/contributions",
        json={"participant_id": participant["id"], "contribution_data": "x"},
    )
    assert response.status_code == 404


def test_submit_contribution_attempt_ceremony_mismatch(client: TestClient) -> None:
    """Attempt belonging to a different ceremony must be rejected."""
    c1 = create_ceremony(client, "Mismatch A")
    c2 = create_ceremony(client, "Mismatch B")
    participant = create_participant(client, c1["id"], "Alice")
    foreign_attempt = create_attempt(client, c2["id"])

    response = client.post(
        f"/ceremonies/{c1['id']}/attempts/{foreign_attempt['id']}/contributions",
        json={"participant_id": participant["id"], "contribution_data": "x"},
    )
    assert response.status_code == 400
    assert "ceremony" in response.json()["detail"].lower()


def test_submit_contribution_participant_not_found(client: TestClient) -> None:
    ceremony, participant, attempt = _setup_ceremony_with_participant_and_attempt(client)
    response = client.post(
        f"/ceremonies/{ceremony['id']}/attempts/{attempt['id']}/contributions",
        json={"participant_id": 999999, "contribution_data": "x"},
    )
    assert response.status_code == 404


def test_submit_contribution_participant_ceremony_mismatch(client: TestClient) -> None:
    """Participant belonging to a different ceremony must be rejected."""
    c1 = create_ceremony(client, "P Mismatch A")
    c2 = create_ceremony(client, "P Mismatch B")
    foreign_participant = create_participant(client, c2["id"], "Bob")
    attempt = create_attempt(client, c1["id"])

    response = client.post(
        f"/ceremonies/{c1['id']}/attempts/{attempt['id']}/contributions",
        json={"participant_id": foreign_participant["id"], "contribution_data": "x"},
    )
    assert response.status_code == 400
    assert "ceremony" in response.json()["detail"].lower()


def test_submit_contribution_validation_error(client: TestClient) -> None:
    ceremony, participant, attempt = _setup_ceremony_with_participant_and_attempt(client)
    response = client.post(
        f"/ceremonies/{ceremony['id']}/attempts/{attempt['id']}/contributions",
        json={"participant_id": participant["id"], "contribution_data": ""},
    )
    assert response.status_code == 422
