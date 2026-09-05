"""Recovery REST API (Phase 4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import (
    ContributionResponse,
    RecoveryResumeRequest,
    RecoveryResumeResponse,
    RecoveryStartResponse,
    RecoveryStatusResponse,
)
from app.services import ceremonies as ceremony_service
from app.services import recovery as recovery_service

router = APIRouter(tags=["recovery"])


@router.post(
    "/ceremonies/{ceremony_id}/recovery/start",
    response_model=RecoveryStartResponse,
    status_code=status.HTTP_200_OK,
    summary="Start recovery for an incomplete ceremony",
)
def start_recovery(
    ceremony_id: int, db: Session = Depends(get_db)
) -> RecoveryStartResponse:
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")
    try:
        result = recovery_service.start_recovery(db, ceremony_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RecoveryStartResponse(
        ceremony_id=ceremony_id,
        ceremony_status=result.ceremony.status,
        recovery_attempt_id=result.recovery_attempt_id,
        message=(
            f"Recovery started. Recovery attempt id={result.recovery_attempt_id}. "
            f"Missing participants can now resume their contributions."
        ),
        recovery_status=result.status,
    )


@router.get(
    "/ceremonies/{ceremony_id}/recovery/status",
    response_model=RecoveryStatusResponse,
    summary="Check ceremony recovery status",
)
def get_recovery_status(
    ceremony_id: int, db: Session = Depends(get_db)
) -> RecoveryStatusResponse:
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")
    try:
        return recovery_service.build_recovery_status(db, ceremony_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/ceremonies/{ceremony_id}/recovery/resume",
    response_model=RecoveryResumeResponse,
    summary="Resume a participant contribution during recovery",
    responses={
        201: {"description": "Contribution accepted during recovery"},
        200: {"description": "Duplicate contribution detected during recovery"},
        409: {"description": "Conflicting contribution detected during recovery"},
    },
)
def resume_participant(
    ceremony_id: int,
    payload: RecoveryResumeRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> RecoveryResumeResponse:
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")

    # Use the latest attempt as the recovery attempt.
    status_resp = recovery_service.build_recovery_status(db, ceremony_id)
    if status_resp.latest_attempt_id is None:
        raise HTTPException(
            status_code=400,
            detail="No attempt exists for this ceremony. Start recovery first.",
        )

    try:
        result = recovery_service.resume_participant(
            db,
            ceremony_id=ceremony_id,
            recovery_attempt_id=status_resp.latest_attempt_id,
            participant_id=payload.participant_id,
            contribution_data=payload.contribution_data,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Set HTTP status based on submission outcome (same as the contribution endpoint).
    if result.status == "accepted":
        response.status_code = status.HTTP_201_CREATED
    elif result.status == "duplicate":
        response.status_code = status.HTTP_200_OK
    elif result.status == "conflict":
        response.status_code = status.HTTP_409_CONFLICT

    updated_status = recovery_service.build_recovery_status(db, ceremony_id)

    contribution_resp = None
    if result.canonical is not None:
        contribution_resp = ContributionResponse.model_validate(result.canonical)

    return RecoveryResumeResponse(
        ceremony_id=ceremony_id,
        participant_id=payload.participant_id,
        submission_status=result.status,
        message=result.message,
        contribution=contribution_resp,
        submitted_hash=result.submitted_hash,
        recovery_status=updated_status,
    )
