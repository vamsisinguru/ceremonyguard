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

from app.models import Contribution, SubmissionRecord
from app.schemas import ContributionCreate
from app.services.audit import record_event

logger = logging.getLogger(__name__)

# Contribution statuses.
STATUS_ACCEPTED = "accepted"
STATUS_DUPLICATE = "duplicate"
STATUS_CONFLICT = "conflict"


def _find_submission_record(
    db: Session, ceremony_id: int, submission_key: str
) -> SubmissionRecord | None:
    """Return the submission record for a given ceremony + submission key."""
    return db.scalar(
        select(SubmissionRecord).where(
            SubmissionRecord.ceremony_id == ceremony_id,
            SubmissionRecord.submission_key == submission_key,
        )
    )


def _record_submission(
    db: Session,
    *,
    ceremony_id: int,
    participant_id: int,
    attempt_id: int,
    submission_key: str,
    contribution: Contribution,
    submission_status: str,
    submitted_hash: str,
) -> SubmissionRecord:
    """Persist a submission record linking the key to the resulting contribution."""
    record = SubmissionRecord(
        ceremony_id=ceremony_id,
        participant_id=participant_id,
        attempt_id=attempt_id,
        submission_key=submission_key,
        contribution_id=contribution.id,
        submission_status=submission_status,
        submitted_hash=submitted_hash,
    )
    db.add(record)
    db.flush()
    return record


@dataclass(frozen=True)
class SubmissionResult:
    """Outcome of a contribution submission."""

    status: str  # accepted | duplicate | conflict
    message: str
    canonical: Contribution  # the canonical accepted contribution
    submitted_hash: str
    # The rejected record (duplicate/conflict). None for accepted submissions.
    # Used by the API to expose the submitted contribution id for the
    # "Why rejected?" explanation without an extra DB lookup.
    submitted_record: Contribution | None = None


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

    If ``payload.submission_key`` is provided and a prior submission with the
    same key already exists, the original result is returned without creating
    a new contribution.  This enables safe retries after a lost response.
    """
    submitted_hash = hash_contribution_data(payload.contribution_data)

    # Idempotency: if a submission_key is provided and already recorded,
    # return the original result without creating a new contribution.
    if payload.submission_key:
        existing_record = _find_submission_record(
            db, ceremony_id, payload.submission_key
        )
        if existing_record is not None:
            original = db.get(Contribution, existing_record.contribution_id)
            if original is not None:
                return SubmissionResult(
                    status=existing_record.submission_status,
                    message=(
                        f"Submission with key '{payload.submission_key}' "
                        f"already processed. Returning original result "
                        f"(contribution id={original.id}, "
                        f"status={existing_record.submission_status})."
                    ),
                    canonical=original
                    if existing_record.submission_status == STATUS_ACCEPTED
                    else _find_canonical(db, ceremony_id, payload.participant_id)
                    or original,
                    submitted_hash=existing_record.submitted_hash,
                    submitted_record=original
                    if existing_record.submission_status != STATUS_ACCEPTED
                    else None,
                )

    # Look for an existing canonical contribution for this ceremony+participant.
    existing = _find_canonical(db, ceremony_id, payload.participant_id)

    if existing is not None:
        if existing.contribution_hash == submitted_hash:
            result = _handle_duplicate(
                db,
                ceremony_id=ceremony_id,
                attempt_id=attempt_id,
                payload=payload,
                submitted_hash=submitted_hash,
                canonical=existing,
            )
        else:
            result = _handle_conflict(
                db,
                ceremony_id=ceremony_id,
                attempt_id=attempt_id,
                payload=payload,
                submitted_hash=submitted_hash,
                canonical=existing,
            )
    else:
        # No existing canonical contribution — try to insert a new accepted one.
        result = _handle_accepted(
            db,
            ceremony_id=ceremony_id,
            attempt_id=attempt_id,
            payload=payload,
            submitted_hash=submitted_hash,
        )

    # Record the submission key for idempotent retries.
    if payload.submission_key:
        _record_submission(
            db,
            ceremony_id=ceremony_id,
            participant_id=payload.participant_id,
            attempt_id=attempt_id,
            submission_key=payload.submission_key,
            contribution=result.canonical
            if result.status == STATUS_ACCEPTED
            else (result.submitted_record or result.canonical),
            submission_status=result.status,
            submitted_hash=submitted_hash,
        )
        db.commit()

    return result


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
    db.refresh(duplicate_record)
    return SubmissionResult(
        status=STATUS_DUPLICATE,
        message=(
            f"Duplicate contribution detected. "
            f"The original contribution (id={canonical.id}) was retained."
        ),
        canonical=canonical,
        submitted_hash=submitted_hash,
        submitted_record=duplicate_record,
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
    db.refresh(conflict_record)
    return SubmissionResult(
        status=STATUS_CONFLICT,
        message=(
            f"Conflict detected. A different contribution was submitted by this "
            f"participant. The original contribution (id={canonical.id}) was retained."
        ),
        canonical=canonical,
        submitted_hash=submitted_hash,
        submitted_record=conflict_record,
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


def get_submission_status(
    db: Session, ceremony_id: int, submission_key: str
) -> tuple[str, Contribution | None, SubmissionRecord | None]:
    """Return the status of a logical submission by its key.

    Returns a tuple of (status_string, contribution, submission_record).
    The status string is one of: ACCEPTED, DUPLICATE, CONFLICT, NOT_FOUND.
    """
    record = _find_submission_record(db, ceremony_id, submission_key)
    if record is None:
        return "NOT_FOUND", None, None
    contribution = db.get(Contribution, record.contribution_id)
    status_upper = record.submission_status.upper()
    return status_upper, contribution, record
