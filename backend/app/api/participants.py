"""Participant REST API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import ParticipantCreate, ParticipantResponse
from app.services import ceremonies as ceremony_service
from app.services import participants as participant_service

router = APIRouter(tags=["participants"])


@router.post(
    "/ceremonies/{ceremony_id}/participants",
    response_model=ParticipantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a participant to a ceremony",
)
def create_participant(
    ceremony_id: int,
    payload: ParticipantCreate,
    db: Session = Depends(get_db),
) -> ParticipantResponse:
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")
    participant = participant_service.create_participant(db, ceremony_id, payload)
    return ParticipantResponse.model_validate(participant)


@router.get(
    "/ceremonies/{ceremony_id}/participants",
    response_model=list[ParticipantResponse],
    summary="List participants in a ceremony",
)
def list_participants(
    ceremony_id: int, db: Session = Depends(get_db)
) -> list[ParticipantResponse]:
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")
    return [
        ParticipantResponse.model_validate(p)
        for p in participant_service.list_participants_for_ceremony(db, ceremony_id)
    ]


@router.get(
    "/participants/{participant_id}",
    response_model=ParticipantResponse,
    summary="Retrieve a participant by ID",
)
def get_participant(
    participant_id: int, db: Session = Depends(get_db)
) -> ParticipantResponse:
    participant = participant_service.get_participant(db, participant_id)
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")
    return ParticipantResponse.model_validate(participant)
