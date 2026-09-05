"""Ceremony attempt REST API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import CeremonyAttemptResponse
from app.services import attempts as attempt_service
from app.services import ceremonies as ceremony_service

router = APIRouter(tags=["attempts"])


@router.post(
    "/ceremonies/{ceremony_id}/attempts",
    response_model=CeremonyAttemptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new attempt for a ceremony",
)
def create_attempt(
    ceremony_id: int, db: Session = Depends(get_db)
) -> CeremonyAttemptResponse:
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")
    attempt = attempt_service.create_attempt(db, ceremony_id)
    return CeremonyAttemptResponse.model_validate(attempt)


@router.get(
    "/ceremonies/{ceremony_id}/attempts",
    response_model=list[CeremonyAttemptResponse],
    summary="List attempts for a ceremony",
)
def list_attempts(
    ceremony_id: int, db: Session = Depends(get_db)
) -> list[CeremonyAttemptResponse]:
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")
    return [
        CeremonyAttemptResponse.model_validate(a)
        for a in attempt_service.list_attempts_for_ceremony(db, ceremony_id)
    ]


@router.get(
    "/attempts/{attempt_id}",
    response_model=CeremonyAttemptResponse,
    summary="Retrieve an attempt by ID",
)
def get_attempt(attempt_id: int, db: Session = Depends(get_db)) -> CeremonyAttemptResponse:
    attempt = attempt_service.get_attempt(db, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return CeremonyAttemptResponse.model_validate(attempt)
