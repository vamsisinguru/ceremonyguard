"""Tests for the Ceremony REST API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import create_ceremony


def test_create_ceremony(client: TestClient) -> None:
    response = client.post("/ceremonies", json={"name": "Signing Ceremony"})
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["name"] == "Signing Ceremony"
    assert body["status"] == "active"
    assert body["created_at"]


def test_create_ceremony_validation_error(client: TestClient) -> None:
    response = client.post("/ceremonies", json={"name": ""})
    assert response.status_code == 422


def test_get_ceremony(client: TestClient) -> None:
    created = create_ceremony(client, "Get Me")
    response = client.get(f"/ceremonies/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_ceremony_not_found(client: TestClient) -> None:
    response = client.get("/ceremonies/999999")
    assert response.status_code == 404


def test_list_ceremonies(client: TestClient) -> None:
    create_ceremony(client, "List A")
    create_ceremony(client, "List B")
    response = client.get("/ceremonies")
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert "List A" in names
    assert "List B" in names


def test_update_ceremony_status(client: TestClient) -> None:
    created = create_ceremony(client, "Status Update")
    response = client.patch(
        f"/ceremonies/{created['id']}/status", json={"status": "completed"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_update_ceremony_status_not_found(client: TestClient) -> None:
    response = client.patch("/ceremonies/999999/status", json={"status": "completed"})
    assert response.status_code == 404
