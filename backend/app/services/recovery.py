"""Recovery service — safe recovery for incomplete ceremonies (Phase 4).

Recovery allows a ceremony to continue when one or more participants failed
to submit their contributions.  Existing canonical contributions are never
modified or removed.  A new attempt is created for the recovery, and
missing participants can resume by submitting their contribution to that
attempt.  The existing Phase 3 duplicate/conflict rules continue to apply
during recovery.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Ceremony, Contribution, Participant
from app.schemas import (
    CanonicalContributionInfo,
    ParticipantContributionStatus,
    RecoveryStatusResponse,
)
from app.services import attempts as attempt_service
from app.services import ceremonies as ceremony_service
from app.services import contributions as contribution_service
from app.services import participants as participant_service
from app.services.audit import record_event
from app.services.verification import get_canonical_set

CEREMONY_STATUS_RECOVERING = "recovering"


@dataclass(frozen=True)
class RecoveryStartResult:
    ceremony: Ceremony
    recovery_attempt_id: int
    status: RecoveryStatusResponse


def start_recovery(db: Session, ceremony_id: int) -> RecoveryStartResult:
    """Start recovery for an incomplete ceremony.

    Creates a new attempt and marks the ceremony as ``recovering``.
    Existing canonical contributions remain unchanged.
    """
    ceremony = ceremony_service.get_ceremony(db, ceremony_id)
    if ceremony is None:
        raise LookupError("Ceremony not found")

    # Create a new attempt for the recovery.
    attempt = attempt_service.create_attempt(db, ceremony_id)

    # Mark the ceremony as recovering.
    ceremony.status = CEREMONY_STATUS_RECOVERING
    db.commit()
    db.refresh(ceremony)

    record_event(
        db,
        ceremony_id=ceremony_id,
        event_type="CEREMONY_RECOVERY_STARTED",
        message=(
            f"Recovery started for ceremony '{ceremony.name}' (id={ceremony_id}). "
            f"Recovery attempt #{attempt.attempt_number} (id={attempt.id}) created."
        ),
    )
    db.commit()

    status = build_recovery_status(db, ceremony_id)
    return RecoveryStartResult(
        ceremony=ceremony,
        recovery_attempt_id=attempt.id,
        status=status,
    )


def resume_participant(
    db: Session,
    ceremony_id: int,
    recovery_attempt_id: int,
    participant_id: int,
    contribution_data: str,
) -> contribution_service.SubmissionResult:
    """Resume a participant's contribution during recovery.

    This uses the existing contribution submission logic, so duplicate/conflict
    rules continue to apply.  A ``PARTICIPANT_RECOVERY_RESUMED`` audit event is
    recorded.
    """
    # Validate relationships (same as the contribution submit endpoint).
    ceremony = ceremony_service.get_ceremony(db, ceremony_id)
    if ceremony is None:
        raise LookupError("Ceremony not found")

    attempt = attempt_service.get_attempt(db, recovery_attempt_id)
    if attempt is None:
        raise LookupError("Attempt not found")
    if attempt.ceremony_id != ceremony_id:
        raise ValueError("Attempt does not belong to the specified ceremony")

    participant = participant_service.get_participant(db, participant_id)
    if participant is None:
        raise LookupError("Participant not found")
    if participant.ceremony_id != ceremony_id:
        raise ValueError("Participant does not belong to the specified ceremony")

    # Use the existing submission logic (handles duplicate/conflict).
    from app.schemas import ContributionCreate

    payload = ContributionCreate(
        participant_id=participant_id,
        contribution_data=contribution_data,
    )
    result = contribution_service.submit_contribution(
        db,
        ceremony_id=ceremony_id,
        attempt_id=recovery_attempt_id,
        payload=payload,
    )

    record_event(
        db,
        ceremony_id=ceremony_id,
        participant_id=participant_id,
        event_type="PARTICIPANT_RECOVERY_RESUMED",
        message=(
            f"Participant '{participant.name}' (id={participant_id}) resumed "
            f"contribution during recovery of ceremony {ceremony_id}. "
            f"Submission status: {result.status}."
        ),
    )
    db.commit()

    return result


def build_recovery_status(db: Session, ceremony_id: int) -> RecoveryStatusResponse:
    """Build the recovery status for a ceremony."""
    ceremony = ceremony_service.get_ceremony(db, ceremony_id)
    if ceremony is None:
        raise LookupError("Ceremony not found")

    canonical_set = get_canonical_set(db, ceremony_id)
    participants = canonical_set.participants
    contributions = {c.participant_id: c for c in canonical_set.contributions}

    complete: list[ParticipantContributionStatus] = []
    incomplete: list[ParticipantContributionStatus] = []

    for p in participants:
        c = contributions.get(p.id)
        if c is not None:
            complete.append(
                ParticipantContributionStatus(
                    participant_id=p.id,
                    participant_name=p.name,
                    has_canonical=True,
                    contribution_id=c.id,
                    contribution_hash=c.contribution_hash,
                    attempt_id=c.attempt_id,
                )
            )
        else:
            incomplete.append(
                ParticipantContributionStatus(
                    participant_id=p.id,
                    participant_name=p.name,
                    has_canonical=False,
                )
            )

    # Get the latest attempt ID.
    attempts = attempt_service.list_attempts_for_ceremony(db, ceremony_id)
    latest_attempt_id = attempts[-1].id if attempts else None

    ready = len(incomplete) == 0 and len(participants) > 0

    return RecoveryStatusResponse(
        ceremony_id=ceremony_id,
        ceremony_name=ceremony.name,
        ceremony_status=ceremony.status,
        ready=ready,
        total_participants=len(participants),
        participants_with_contribution=len(complete),
        incomplete_participants=incomplete,
        complete_participants=complete,
        latest_attempt_id=latest_attempt_id,
    )
