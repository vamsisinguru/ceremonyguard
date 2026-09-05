"""Contribution service — submission, retrieval, and SHA-256 fingerprinting."""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Contribution
from app.schemas import ContributionCreate
from app.services.audit import record_event


def submit_contribution(
    db: Session,
    *,
    ceremony_id: int,
    attempt_id: int,
    payload: ContributionCreate,
) -> Contribution:
    """Persist a contribution with a deterministic SHA-256 hash of its data.

    Relationship validation (ceremony/attempt/participant existence and
    belonging) is performed by the route layer before calling this service.
    Duplicate/conflict detection is intentionally deferred to Phase 3.
    """
    contribution_hash = hash_contribution_data(payload.contribution_data)
    contribution = Contribution(
        ceremony_id=ceremony_id,
        attempt_id=attempt_id,
        participant_id=payload.participant_id,
        contribution_hash=contribution_hash,
        contribution_data=payload.contribution_data,
        status="accepted",
    )
    db.add(contribution)
    db.flush()
    record_event(
        db,
        ceremony_id=ceremony_id,
        participant_id=payload.participant_id,
        event_type="contribution_submitted",
        message=(
            f"Contribution {contribution.id} submitted for attempt {attempt_id} "
            f"by participant {payload.participant_id} (hash={contribution_hash})"
        ),
    )
    db.commit()
    db.refresh(contribution)
    return contribution


def get_contribution(db: Session, contribution_id: int) -> Contribution | None:
    return db.get(Contribution, contribution_id)


def list_contributions_for_attempt(
    db: Session, ceremony_id: int, attempt_id: int
) -> list[Contribution]:
    return list(
        db.scalars(
            select(Contribution)
            .where(
                Contribution.ceremony_id == ceremony_id,
                Contribution.attempt_id == attempt_id,
            )
            .order_by(Contribution.id)
        )
    )


def hash_contribution_data(data: str) -> str:
    """Return the SHA-256 hex digest of the contribution data."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
