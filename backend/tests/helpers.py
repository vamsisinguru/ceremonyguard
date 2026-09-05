"""Shared helpers for Phase 2/3 tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def create_ceremony(client: TestClient, name: str = "Test Ceremony") -> dict:
    response = client.post("/ceremonies", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def create_participant(client: TestClient, ceremony_id: int, name: str = "Alice") -> dict:
    response = client.post(
        f"/ceremonies/{ceremony_id}/participants", json={"name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_attempt(client: TestClient, ceremony_id: int) -> dict:
    response = client.post(f"/ceremonies/{ceremony_id}/attempts")
    assert response.status_code == 201, response.text
    return response.json()


def submit_contribution(
    client: TestClient,
    ceremony_id: int,
    attempt_id: int,
    participant_id: int,
    data: str = "sample-contribution-data",
) -> dict:
    """Submit a contribution and return the full response body.

    The response is a ``ContributionSubmissionResponse`` with fields:
    ``status``, ``message``, ``ceremony_id``, ``participant_id``,
    ``contribution`` (nested ``ContributionResponse``), ``submitted_hash``.
    """
    response = client.post(
        f"/ceremonies/{ceremony_id}/attempts/{attempt_id}/contributions",
        json={"participant_id": participant_id, "contribution_data": data},
    )
    return response.json()


def submit_contribution_raw(
    client: TestClient,
    ceremony_id: int,
    attempt_id: int,
    participant_id: int,
    data: str = "sample-contribution-data",
):
    """Submit a contribution and return the raw ``Response`` object."""
    return client.post(
        f"/ceremonies/{ceremony_id}/attempts/{attempt_id}/contributions",
        json={"participant_id": participant_id, "contribution_data": data},
    )
