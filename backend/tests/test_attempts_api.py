"""Tests for the Ceremony Attempt REST API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import create_attempt, create_ceremony


def test_create_first_attempt(client: TestClient) -> None:
    ceremony = create_ceremony(client, "Attempt Ceremony")
    response = client.post(f"/ceremonies/{ceremony['id']}/attempts")
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["ceremony_id"] == ceremony["id"]
    assert body["attempt_number"] == 1
    assert body["status"] == "active"
    assert body["created_at"]


def test_attempt_numbers_increment(client: TestClient) -> None:
    ceremony = create_ceremony(client, "Increment Ceremony")
    a1 = create_attempt(client, ceremony["id"])
    a2 = create_attempt(client, ceremony["id"])
    a3 = create_attempt(client, ceremony["id"])
    assert a1["attempt_number"] == 1
    assert a2["attempt_number"] == 2
    assert a3["attempt_number"] == 3


def test_attempts_are_independent_per_ceremony(client: TestClient) -> None:
    c1 = create_ceremony(client, "Independent A")
    c2 = create_ceremony(client, "Independent B")
    a1 = create_attempt(client, c1["id"])
    a2 = create_attempt(client, c2["id"])
    assert a1["attempt_number"] == 1
    assert a2["attempt_number"] == 1
    assert a1["ceremony_id"] == c1["id"]
    assert a2["ceremony_id"] == c2["id"]


def test_list_attempts(client: TestClient) -> None:
    ceremony = create_ceremony(client, "List Attempts")
    create_attempt(client, ceremony["id"])
    create_attempt(client, ceremony["id"])
    response = client.get(f"/ceremonies/{ceremony['id']}/attempts")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["attempt_number"] == 1
    assert body[1]["attempt_number"] == 2


def test_create_attempt_ceremony_not_found(client: TestClient) -> None:
    response = client.post("/ceremonies/999999/attempts")
    assert response.status_code == 404


def test_list_attempts_ceremony_not_found(client: TestClient) -> None:
    response = client.get("/ceremonies/999999/attempts")
    assert response.status_code == 404


def test_get_attempt(client: TestClient) -> None:
    ceremony = create_ceremony(client, "Get Attempt")
    attempt = create_attempt(client, ceremony["id"])
    response = client.get(f"/attempts/{attempt['id']}")
    assert response.status_code == 200
    assert response.json() == attempt


def test_get_attempt_not_found(client: TestClient) -> None:
    response = client.get("/attempts/999999")
    assert response.status_code == 404


def test_attempt_cannot_be_associated_with_another_ceremony(client: TestClient) -> None:
    """An attempt stored under ceremony A must report ceremony_id == A."""
    c1 = create_ceremony(client, "Owner A")
    c2 = create_ceremony(client, "Owner B")
    attempt = create_attempt(client, c1["id"])
    fetched = client.get(f"/attempts/{attempt['id']}").json()
    assert fetched["ceremony_id"] == c1["id"]
    assert fetched["ceremony_id"] != c2["id"]
