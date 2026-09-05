"""Tests for the Participant REST API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import create_ceremony, create_participant


def test_create_participant(client: TestClient) -> None:
    ceremony = create_ceremony(client, "Participant Ceremony")
    response = client.post(
        f"/ceremonies/{ceremony['id']}/participants", json={"name": "Alice"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["ceremony_id"] == ceremony["id"]
    assert body["name"] == "Alice"
    assert body["status"] == "active"
    assert body["created_at"]


def test_create_participant_ceremony_not_found(client: TestClient) -> None:
    response = client.post("/ceremonies/999999/participants", json={"name": "Bob"})
    assert response.status_code == 404


def test_list_participants(client: TestClient) -> None:
    ceremony = create_ceremony(client, "List Participants")
    create_participant(client, ceremony["id"], "Alice")
    create_participant(client, ceremony["id"], "Bob")
    response = client.get(f"/ceremonies/{ceremony['id']}/participants")
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert names == ["Alice", "Bob"]


def test_list_participants_only_returns_own_ceremony(client: TestClient) -> None:
    c1 = create_ceremony(client, "Ceremony One")
    c2 = create_ceremony(client, "Ceremony Two")
    create_participant(client, c1["id"], "Alice")
    create_participant(client, c2["id"], "Bob")

    response = client.get(f"/ceremonies/{c1['id']}/participants")
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert names == ["Alice"]
    assert "Bob" not in names


def test_list_participants_ceremony_not_found(client: TestClient) -> None:
    response = client.get("/ceremonies/999999/participants")
    assert response.status_code == 404


def test_get_participant(client: TestClient) -> None:
    ceremony = create_ceremony(client, "Get Participant")
    participant = create_participant(client, ceremony["id"], "Alice")
    response = client.get(f"/participants/{participant['id']}")
    assert response.status_code == 200
    assert response.json() == participant


def test_get_participant_not_found(client: TestClient) -> None:
    response = client.get("/participants/999999")
    assert response.status_code == 404


def test_participant_belongs_to_correct_ceremony(client: TestClient) -> None:
    ceremony = create_ceremony(client, "Belongs To")
    participant = create_participant(client, ceremony["id"], "Alice")
    fetched = client.get(f"/participants/{participant['id']}").json()
    assert fetched["ceremony_id"] == ceremony["id"]
