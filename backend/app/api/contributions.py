"""Contribution REST API.

Phase 2 only validates relationships and stores the contribution with a
SHA-256 fingerprint. Duplicate/conflict detection is deferred to Phase 3.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import ContributionCreate, ContributionResponse
from app.services import attempts as attempt_service
from app.services import ceremonies as ceremony_service
from app.services import contributions as contribution_service
from app.services import participants as participant_service

router = APIRouter(tags=["contributions"])


@router.post(
    "/ceremonies/{ceremony_id}/attempts/{attempt_id}/contributions",
    response_model=ContributionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a contribution to a ceremony attempt",
)
def submit_contribution(
    ceremony_id: int,
    attempt_id: int,
    payload: ContributionCreate,
    db: Session = Depends(get_db),
) -> ContributionResponse:
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

    contribution = contribution_service.submit_contribution(
        db,
        ceremony_id=ceremony_id,
        attempt_id=attempt_id,
        payload=payload,
    )
    return ContributionResponse.model_validate(contribution)


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
