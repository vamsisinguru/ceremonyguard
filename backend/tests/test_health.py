"""Tests for the /health endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    """GET /health should return 200 with status=ok and app metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "CeremonyGuard"
    assert "environment" in body
