"""Final verification REST API (Phase 4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import (
    CanonicalContributionInfo,
    FinalResultResponse,
)
from app.services import ceremonies as ceremony_service
from app.services import verification as verification_service

router = APIRouter(tags=["verification"])


def _build_response(
    db: Session, ceremony_id: int
) -> FinalResultResponse:
    """Build the final result response from current state."""
    ceremony = ceremony_service.get_ceremony(db, ceremony_id)
    if ceremony is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")

    canonical_set = verification_service.get_canonical_set(db, ceremony_id)
    stored = verification_service.get_stored_result(db, ceremony_id)
    ready = verification_service.is_ceremony_ready(db, ceremony_id)

    # Build participant lookup for names.
    participant_map = {p.id: p.name for p in canonical_set.participants}

    canonical_infos = [
        CanonicalContributionInfo(
            contribution_id=c.id,
            participant_id=c.participant_id,
            participant_name=participant_map.get(c.participant_id, f"#{c.participant_id}"),
            attempt_id=c.attempt_id,
            contribution_hash=c.contribution_hash,
        )
        for c in canonical_set.contributions
    ]

    if stored is None:
        if ready:
            return FinalResultResponse(
                ceremony_id=ceremony_id,
                ceremony_name=ceremony.name,
                ceremony_status=ceremony.status,
                ready=True,
                generated=False,
                verified=False,
                verification_status="not_generated",
                canonical_contributions=canonical_infos,
                message="Ceremony is ready but the final result has not been generated yet.",
            )
        return FinalResultResponse(
            ceremony_id=ceremony_id,
            ceremony_name=ceremony.name,
            ceremony_status=ceremony.status,
            ready=False,
            generated=False,
            verified=False,
            verification_status="not_ready",
            canonical_contributions=canonical_infos,
            message="Ceremony is not ready: not all participants have canonical contributions.",
        )

    # A stored result exists — verify it.
    verified, verify_message = verification_service.verify_final_result(db, ceremony_id)
    verification_status = "verified" if verified else "verification_failed"

    return FinalResultResponse(
        ceremony_id=ceremony_id,
        ceremony_name=ceremony.name,
        ceremony_status=ceremony.status,
        ready=ready,
        generated=True,
        verified=verified,
        verification_status=verification_status,
        final_digest=stored.final_digest,
        contribution_digest=stored.contribution_digest,
        participant_count=stored.participant_count,
        canonical_contributions=canonical_infos,
        message=verify_message,
        created_at=stored.created_at,
    )


@router.post(
    "/ceremonies/{ceremony_id}/finalize",
    response_model=FinalResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate the final result for a completed ceremony",
)
def finalize_ceremony(
    ceremony_id: int, db: Session = Depends(get_db)
) -> FinalResultResponse:
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")

    try:
        verification_service.generate_final_result(db, ceremony_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _build_response(db, ceremony_id)


@router.get(
    "/ceremonies/{ceremony_id}/verification",
    response_model=FinalResultResponse,
    summary="Get final verification status for a ceremony",
)
def get_verification(
    ceremony_id: int, db: Session = Depends(get_db)
) -> FinalResultResponse:
    return _build_response(db, ceremony_id)


@router.post(
    "/ceremonies/{ceremony_id}/verify",
    response_model=FinalResultResponse,
    summary="Verify the final result of a ceremony",
)
def verify_ceremony(
    ceremony_id: int, db: Session = Depends(get_db)
) -> FinalResultResponse:
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")

    stored = verification_service.get_stored_result(db, ceremony_id)
    if stored is None:
        raise HTTPException(
            status_code=400,
            detail="Final result has not been generated. Finalize the ceremony first.",
        )

    return _build_response(db, ceremony_id)
