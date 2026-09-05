"""Ceremony attempt service — business logic for attempts."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CeremonyAttempt
from app.services.audit import record_event


def create_attempt(db: Session, ceremony_id: int) -> CeremonyAttempt:
    next_number = _next_attempt_number(db, ceremony_id)
    attempt = CeremonyAttempt(
        ceremony_id=ceremony_id, attempt_number=next_number, status="active"
    )
    db.add(attempt)
    db.flush()
    record_event(
        db,
        ceremony_id=ceremony_id,
        event_type="attempt_created",
        message=f"Attempt #{attempt.attempt_number} created for ceremony {ceremony_id}",
    )
    db.commit()
    db.refresh(attempt)
    return attempt


def get_attempt(db: Session, attempt_id: int) -> CeremonyAttempt | None:
    return db.get(CeremonyAttempt, attempt_id)


def list_attempts_for_ceremony(db: Session, ceremony_id: int) -> list[CeremonyAttempt]:
    return list(
        db.scalars(
            select(CeremonyAttempt)
            .where(CeremonyAttempt.ceremony_id == ceremony_id)
            .order_by(CeremonyAttempt.attempt_number)
        )
    )


def _next_attempt_number(db: Session, ceremony_id: int) -> int:
    current_max = db.scalar(
        select(func.max(CeremonyAttempt.attempt_number)).where(
            CeremonyAttempt.ceremony_id == ceremony_id
        )
    )
    return (current_max or 0) + 1
