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
    assert body["id"] > 0
    assert body["ceremony_id"] == ceremony["id"]
    assert body["attempt_id"] == attempt["id"]
    assert body["participant_id"] == participant["id"]
    assert body["contribution_data"] == "hello"
    assert body["status"] == "accepted"
    assert body["created_at"]


def test_contribution_sha256_hash_is_correct(client: TestClient) -> None:
    ceremony, participant, attempt = _setup_ceremony_with_participant_and_attempt(client)
    body = submit_contribution(
        client, ceremony["id"], attempt["id"], participant["id"], "hello"
    )
    expected = hashlib.sha256(b"hello").hexdigest()
    assert body["contribution_hash"] == expected
    assert len(body["contribution_hash"]) == 64


def test_contribution_hash_is_deterministic(client: TestClient) -> None:
    ceremony, participant, attempt = _setup_ceremony_with_participant_and_attempt(client)
    b1 = submit_contribution(
        client, ceremony["id"], attempt["id"], participant["id"], "same-data"
    )
    b2 = submit_contribution(
        client, ceremony["id"], attempt["id"], participant["id"], "same-data"
    )
    assert b1["contribution_hash"] == b2["contribution_hash"]


def test_get_contribution(client: TestClient) -> None:
    ceremony, participant, attempt = _setup_ceremony_with_participant_and_attempt(client)
    created = submit_contribution(
        client, ceremony["id"], attempt["id"], participant["id"], "payload"
    )
    response = client.get(f"/contributions/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


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
