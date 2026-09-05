"""Ceremony service — business logic for ceremony lifecycle."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ceremony
from app.schemas import CeremonyCreate, CeremonyStatusUpdate
from app.services.audit import record_event


def create_ceremony(db: Session, payload: CeremonyCreate) -> Ceremony:
    ceremony = Ceremony(name=payload.name, status="active")
    db.add(ceremony)
    db.flush()
    record_event(
        db,
        ceremony_id=ceremony.id,
        event_type="ceremony_created",
        message=f"Ceremony '{ceremony.name}' created",
    )
    db.commit()
    db.refresh(ceremony)
    return ceremony


def get_ceremony(db: Session, ceremony_id: int) -> Ceremony | None:
    return db.get(Ceremony, ceremony_id)


def list_ceremonies(db: Session) -> list[Ceremony]:
    return list(db.scalars(select(Ceremony).order_by(Ceremony.id)))


def update_ceremony_status(
    db: Session, ceremony: Ceremony, payload: CeremonyStatusUpdate
) -> Ceremony:
    ceremony.status = payload.status
    record_event(
        db,
        ceremony_id=ceremony.id,
        event_type="ceremony_status_updated",
        message=f"Ceremony '{ceremony.name}' status set to '{payload.status}'",
    )
    db.commit()
    db.refresh(ceremony)
    return ceremony
