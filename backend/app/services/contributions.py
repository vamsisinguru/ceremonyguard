"""Contribution service — submission, retrieval, and SHA-256 fingerprinting.

Phase 3 adds duplicate and conflict detection:

- **Duplicate**: the same participant submits a contribution with the same
  SHA-256 hash as the existing canonical (``accepted``) contribution for the
  same ceremony.  The original is retained; the retry is recorded with
  status ``duplicate`` for audit history but never becomes canonical.

- **Conflict**: the same participant submits a contribution with a different
  SHA-256 hash.  The original is retained; the conflicting submission is
  recorded with status ``conflict`` for audit history but never becomes
  canonical.

A partial unique index at the database level
(see ``Contribution.__table_args__``) guarantees that at most one
``accepted`` contribution exists per (ceremony, participant) pair, even
under concurrent submissions.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Contribution
from app.schemas import ContributionCreate
from app.services.audit import record_event

logger = logging.getLogger(__name__)

# Contribution statuses.
STATUS_ACCEPTED = "accepted"
STATUS_DUPLICATE = "duplicate"
STATUS_CONFLICT = "conflict"


@dataclass(frozen=True)
class SubmissionResult:
    """Outcome of a contribution submission."""

    status: str  # accepted | duplicate | conflict
    message: str
    canonical: Contribution  # the canonical accepted contribution
    submitted_hash: str


def submit_contribution(
    db: Session,
    *,
    ceremony_id: int,
    attempt_id: int,
    payload: ContributionCreate,
) -> SubmissionResult:
    """Process a contribution submission with duplicate/conflict detection.

    Relationship validation (ceremony/attempt/participant existence and
    belonging) is performed by the route layer before calling this service.
    """
    submitted_hash = hash_contribution_data(payload.contribution_data)

    # Look for an existing canonical contribution for this ceremony+participant.
    existing = _find_canonical(db, ceremony_id, payload.participant_id)

    if existing is not None:
        if existing.contribution_hash == submitted_hash:
            return _handle_duplicate(
                db,
                ceremony_id=ceremony_id,
                attempt_id=attempt_id,
                payload=payload,
                submitted_hash=submitted_hash,
                canonical=existing,
            )
        return _handle_conflict(
            db,
            ceremony_id=ceremony_id,
            attempt_id=attempt_id,
            payload=payload,
            submitted_hash=submitted_hash,
            canonical=existing,
        )

    # No existing canonical contribution — try to insert a new accepted one.
    return _handle_accepted(
        db,
        ceremony_id=ceremony_id,
        attempt_id=attempt_id,
        payload=payload,
        submitted_hash=submitted_hash,
    )


def _handle_accepted(
    db: Session,
    *,
    ceremony_id: int,
    attempt_id: int,
    payload: ContributionCreate,
    submitted_hash: str,
) -> SubmissionResult:
    """Persist a new canonical contribution (status=accepted)."""
    contribution = Contribution(
        ceremony_id=ceremony_id,
        attempt_id=attempt_id,
        participant_id=payload.participant_id,
        contribution_hash=submitted_hash,
        contribution_data=payload.contribution_data,
        status=STATUS_ACCEPTED,
    )
    db.add(contribution)
    try:
        db.flush()
    except IntegrityError:
        # Race condition: another request inserted an accepted contribution
        # for the same ceremony+participant between our check and insert.
        db.rollback()
        existing = _find_canonical(db, ceremony_id, payload.participant_id)
        if existing is None:
            # Should not happen, but handle gracefully.
            raise
        if existing.contribution_hash == submitted_hash:
            return _handle_duplicate(
                db,
                ceremony_id=ceremony_id,
                attempt_id=attempt_id,
                payload=payload,
                submitted_hash=submitted_hash,
                canonical=existing,
            )
        return _handle_conflict(
            db,
            ceremony_id=ceremony_id,
            attempt_id=attempt_id,
            payload=payload,
            submitted_hash=submitted_hash,
            canonical=existing,
        )

    record_event(
        db,
        ceremony_id=ceremony_id,
        participant_id=payload.participant_id,
        event_type="contribution_submitted",
        message=(
            f"Contribution {contribution.id} accepted for ceremony {ceremony_id} "
            f"by participant {payload.participant_id} (hash={submitted_hash})"
        ),
    )
    db.commit()
    db.refresh(contribution)
    return SubmissionResult(
        status=STATUS_ACCEPTED,
        message="Contribution accepted.",
        canonical=contribution,
        submitted_hash=submitted_hash,
    )


def _handle_duplicate(
    db: Session,
    *,
    ceremony_id: int,
    attempt_id: int,
    payload: ContributionCreate,
    submitted_hash: str,
    canonical: Contribution,
) -> SubmissionResult:
    """Record a duplicate submission and retain the original canonical one."""
    duplicate_record = Contribution(
        ceremony_id=ceremony_id,
        attempt_id=attempt_id,
        participant_id=payload.participant_id,
        contribution_hash=submitted_hash,
        contribution_data=payload.contribution_data,
        status=STATUS_DUPLICATE,
    )
    db.add(duplicate_record)
    db.flush()
    record_event(
        db,
        ceremony_id=ceremony_id,
        participant_id=payload.participant_id,
        event_type="CONTRIBUTION_DUPLICATE",
        message=(
            f"Duplicate contribution detected for ceremony {ceremony_id} "
            f"by participant {payload.participant_id}. "
            f"Original contribution {canonical.id} retained. "
            f"Duplicate submission {duplicate_record.id} ignored."
        ),
    )
    db.commit()
    db.refresh(canonical)
    return SubmissionResult(
        status=STATUS_DUPLICATE,
        message=(
            f"Duplicate contribution detected. "
            f"The original contribution (id={canonical.id}) was retained."
        ),
        canonical=canonical,
        submitted_hash=submitted_hash,
    )


def _handle_conflict(
    db: Session,
    *,
    ceremony_id: int,
    attempt_id: int,
    payload: ContributionCreate,
    submitted_hash: str,
    canonical: Contribution,
) -> SubmissionResult:
    """Record a conflicting submission and retain the original canonical one."""
    conflict_record = Contribution(
        ceremony_id=ceremony_id,
        attempt_id=attempt_id,
        participant_id=payload.participant_id,
        contribution_hash=submitted_hash,
        contribution_data=payload.contribution_data,
        status=STATUS_CONFLICT,
    )
    db.add(conflict_record)
    db.flush()
    record_event(
        db,
        ceremony_id=ceremony_id,
        participant_id=payload.participant_id,
        event_type="CONTRIBUTION_CONFLICT",
        message=(
            f"Conflict detected for ceremony {ceremony_id} "
            f"by participant {payload.participant_id}. "
            f"Original contribution {canonical.id} retained (hash={canonical.contribution_hash}). "
            f"Conflicting submission {conflict_record.id} rejected (hash={submitted_hash})."
        ),
    )
    db.commit()
    db.refresh(canonical)
    return SubmissionResult(
        status=STATUS_CONFLICT,
        message=(
            f"Conflict detected. A different contribution was submitted by this "
            f"participant. The original contribution (id={canonical.id}) was retained."
        ),
        canonical=canonical,
        submitted_hash=submitted_hash,
    )


def _find_canonical(
    db: Session, ceremony_id: int, participant_id: int
) -> Contribution | None:
    """Return the canonical (accepted) contribution for a ceremony+participant."""
    return db.scalar(
        select(Contribution).where(
            Contribution.ceremony_id == ceremony_id,
            Contribution.participant_id == participant_id,
            Contribution.status == STATUS_ACCEPTED,
        )
    )


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


def list_contributions_for_ceremony(
    db: Session, ceremony_id: int
) -> list[Contribution]:
    """Return all contributions for a ceremony, ordered by id."""
    return list(
        db.scalars(
            select(Contribution)
            .where(Contribution.ceremony_id == ceremony_id)
            .order_by(Contribution.id)
        )
    )


def hash_contribution_data(data: str) -> str:
    """Return the SHA-256 hex digest of the contribution data."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
