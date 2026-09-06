"""Contribution REST API.

Phase 3 adds duplicate and conflict detection.  The submit endpoint returns
a :class:`ContributionSubmissionResponse` whose ``status`` field is one of
``accepted``, ``duplicate``, or ``conflict``.

- ``accepted``  → HTTP 201 (first contribution)
- ``duplicate`` → HTTP 200 (idempotent retry with identical data)
- ``conflict``  → HTTP 409 (different data from the same participant)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import (
    ContributionCreate,
    ContributionResponse,
    ContributionSubmissionResponse,
)
from app.services import attempts as attempt_service
from app.services import ceremonies as ceremony_service
from app.services import contributions as contribution_service
from app.services import participants as participant_service

router = APIRouter(tags=["contributions"])


@router.post(
    "/ceremonies/{ceremony_id}/attempts/{attempt_id}/contributions",
    response_model=ContributionSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a contribution to a ceremony attempt",
    responses={
        201: {"description": "Contribution accepted"},
        200: {"description": "Duplicate contribution detected"},
        409: {"description": "Conflicting contribution detected"},
    },
)
def submit_contribution(
    ceremony_id: int,
    attempt_id: int,
    payload: ContributionCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> ContributionSubmissionResponse:
    # 1. Ceremony must exist.
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")

    # 2. Attempt must exist.
    attempt = attempt_service.get_attempt(db, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")

    # 3. Attempt must belong to the requested ceremony.
    if attempt.ceremony_id != ceremony_id:
        raise HTTPException(
            status_code=400,
            detail="Attempt does not belong to the specified ceremony",
        )

    # 4. Participant must exist.
    participant = participant_service.get_participant(db, payload.participant_id)
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")

    # 5. Participant must belong to the requested ceremony.
    if participant.ceremony_id != ceremony_id:
        raise HTTPException(
            status_code=400,
            detail="Participant does not belong to the specified ceremony",
        )

    result = contribution_service.submit_contribution(
        db,
        ceremony_id=ceremony_id,
        attempt_id=attempt_id,
        payload=payload,
    )

    # Override the default 201 status code for duplicate/conflict outcomes.
    if result.status == "duplicate":
        response.status_code = status.HTTP_200_OK
    elif result.status == "conflict":
        response.status_code = status.HTTP_409_CONFLICT

    # Populate the optional "Why rejected?" fields for duplicate/conflict.
    original_contribution_id = None
    submitted_contribution_id = None
    original_hash = None
    reason = None
    if result.status in ("duplicate", "conflict"):
        original_contribution_id = result.canonical.id
        original_hash = result.canonical.contribution_hash
        if result.submitted_record is not None:
            submitted_contribution_id = result.submitted_record.id
        if result.status == "duplicate":
            reason = (
                "This participant already submitted a contribution with the "
                "same SHA-256 fingerprint for this ceremony. The original "
                "contribution remains canonical."
            )
        else:
            reason = (
                "This participant already has a canonical contribution, but "
                "the new submission contains different data (different "
                "SHA-256 fingerprint). The original contribution remains "
                "canonical and the new submission was rejected."
            )

    return ContributionSubmissionResponse(
        status=result.status,
        message=result.message,
        ceremony_id=ceremony_id,
        participant_id=payload.participant_id,
        contribution=ContributionResponse.model_validate(result.canonical),
        submitted_hash=result.submitted_hash,
        original_contribution_id=original_contribution_id,
        submitted_contribution_id=submitted_contribution_id,
        original_hash=original_hash,
        reason=reason,
    )


@router.get(
    "/ceremonies/{ceremony_id}/attempts/{attempt_id}/contributions",
    response_model=list[ContributionResponse],
    summary="List contributions for a ceremony attempt",
)
def list_contributions(
    ceremony_id: int,
    attempt_id: int,
    db: Session = Depends(get_db),
) -> list[ContributionResponse]:
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")
    attempt = attempt_service.get_attempt(db, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.ceremony_id != ceremony_id:
        raise HTTPException(
            status_code=400,
            detail="Attempt does not belong to the specified ceremony",
        )
    return [
        ContributionResponse.model_validate(c)
        for c in contribution_service.list_contributions_for_attempt(
            db, ceremony_id, attempt_id
        )
    ]


@router.get(
    "/ceremonies/{ceremony_id}/contributions",
    response_model=list[ContributionResponse],
    summary="List all contributions for a ceremony",
)
def list_ceremony_contributions(
    ceremony_id: int, db: Session = Depends(get_db)
) -> list[ContributionResponse]:
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")
    return [
        ContributionResponse.model_validate(c)
        for c in contribution_service.list_contributions_for_ceremony(db, ceremony_id)
    ]


@router.get(
    "/contributions/{contribution_id}",
    response_model=ContributionResponse,
    summary="Retrieve a contribution by ID",
)
def get_contribution(
    contribution_id: int, db: Session = Depends(get_db)
) -> ContributionResponse:
    contribution = contribution_service.get_contribution(db, contribution_id)
    if contribution is None:
        raise HTTPException(status_code=404, detail="Contribution not found")
    return ContributionResponse.model_validate(contribution)
