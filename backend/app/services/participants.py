"""Participant service — business logic for participants."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Participant
from app.schemas import ParticipantCreate
from app.services.audit import record_event


def create_participant(
    db: Session, ceremony_id: int, payload: ParticipantCreate
) -> Participant:
    participant = Participant(ceremony_id=ceremony_id, name=payload.name, status="active")
    db.add(participant)
    db.flush()
    record_event(
        db,
        ceremony_id=ceremony_id,
        participant_id=participant.id,
        event_type="participant_created",
        message=f"Participant '{participant.name}' added to ceremony {ceremony_id}",
    )
    db.commit()
    db.refresh(participant)
    return participant


def get_participant(db: Session, participant_id: int) -> Participant | None:
    return db.get(Participant, participant_id)


def list_participants_for_ceremony(db: Session, ceremony_id: int) -> list[Participant]:
    return list(
        db.scalars(
            select(Participant)
            .where(Participant.ceremony_id == ceremony_id)
            .order_by(Participant.id)
        )
    )
