"""Tests that the FastAPI application starts up correctly."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_app_starts(client: TestClient) -> None:
    """The FastAPI app should instantiate and expose a root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "CeremonyGuard"
    assert body["phase"] == "3"


def test_openapi_schema_available(client: TestClient) -> None:
    """The auto-generated OpenAPI schema should be reachable."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "CeremonyGuard"
