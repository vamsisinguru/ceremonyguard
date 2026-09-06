"""Smart Ceremony Monitoring & Automatic Recovery service.

This service provides:

1. **Submission status lookup** — check whether a logical submission
   (identified by its ``submission_key``) has already been processed.
2. **Ceremony monitoring** — assess the overall state of a ceremony and
   identify participants with unresolved submissions, conflicts, or missing
   contributions.
3. **Recovery reports** — generate an incident report explaining what happened
   during an unresolved submission and what action (automatic or manual) is
   required.

Design principles:

- The system monitors **server-side ceremony state**, not the participant's
  physical network connection.
- Automatic recovery is conservative: it only confirms existing accepted
  contributions or safely retries the same logical submission.  It never
  replaces an accepted canonical contribution, invents data, or chooses
  between conflicting contributions.
- When the state cannot be safely determined, the system stops and generates
  a manual-action report.
- All recovery actions are recorded in the existing audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Contribution
from app.schemas import (
    CeremonyMonitorResponse,
    ParticipantMonitorStatus,
    RecoveryReportRequest,
    RecoveryReportResponse,
    SubmissionStatusResponse,
)
from app.services import ceremonies as ceremony_service
from app.services import contributions as contribution_service
from app.services import participants as participant_service
from app.services.audit import record_event
from app.services.verification import get_canonical_set, get_stored_result


# --------------------------------------------------------------------------- #
# Submission status lookup
# --------------------------------------------------------------------------- #
def get_submission_status_response(
    db: Session, ceremony_id: int, submission_key: str
) -> SubmissionStatusResponse:
    """Return the status of a logical submission by its key."""
    ceremony = ceremony_service.get_ceremony(db, ceremony_id)
    if ceremony is None:
        raise LookupError("Ceremony not found")

    status, contribution, record = contribution_service.get_submission_status(
        db, ceremony_id, submission_key
    )

    if record is None or contribution is None:
        return SubmissionStatusResponse(
            ceremony_id=ceremony_id,
            submission_key=submission_key,
            status="NOT_FOUND",
            message=(
                f"No submission found for key '{submission_key}' in "
                f"ceremony {ceremony_id}. The submission may not have reached "
                f"the server."
            ),
        )

    return SubmissionStatusResponse(
        ceremony_id=ceremony_id,
        submission_key=submission_key,
        status=status,
        contribution_id=contribution.id,
        participant_id=record.participant_id,
        attempt_id=record.attempt_id,
        contribution_hash=contribution.contribution_hash,
        message=(
            f"Submission '{submission_key}' found with status {status} "
            f"(contribution id={contribution.id})."
        ),
    )


# --------------------------------------------------------------------------- #
# Ceremony monitoring
# --------------------------------------------------------------------------- #
def get_ceremony_monitor(
    db: Session, ceremony_id: int
) -> CeremonyMonitorResponse:
    """Assess the overall state of a ceremony for monitoring purposes."""
    ceremony = ceremony_service.get_ceremony(db, ceremony_id)
    if ceremony is None:
        raise LookupError("Ceremony not found")

    canonical_set = get_canonical_set(db, ceremony_id)
    participants = canonical_set.participants
    canonical_by_participant = {
        c.participant_id: c for c in canonical_set.contributions
    }

    # Count duplicate/conflict records for the ceremony.
    all_contributions = contribution_service.list_contributions_for_ceremony(
        db, ceremony_id
    )
    conflict_count = sum(1 for c in all_contributions if c.status == "conflict")
    duplicate_count = sum(
        1 for c in all_contributions if c.status == "duplicate"
    )

    # Check final result / verification state.
    stored_result = get_stored_result(db, ceremony_id)
    has_final_result = stored_result is not None
    verified: bool | None = None
    if has_final_result:
        # Re-derive verification status by comparing digests.
        from app.services.verification import (
            _build_contribution_digest,
            _compute_final_digest,
        )

        current_cd = _build_contribution_digest(canonical_set.contributions)
        current_fd = _compute_final_digest(ceremony_id, canonical_set.contributions)
        verified = (
            current_cd == stored_result.contribution_digest
            and current_fd == stored_result.final_digest
        )

    # Build per-participant status.
    participant_statuses: list[ParticipantMonitorStatus] = []
    incomplete_count = 0
    issues: list[str] = []

    for p in participants:
        canonical = canonical_by_participant.get(p.id)
        if canonical is not None:
            participant_statuses.append(
                ParticipantMonitorStatus(
                    participant_id=p.id,
                    participant_name=p.name,
                    has_canonical=True,
                    contribution_id=canonical.id,
                    attempt_id=canonical.attempt_id,
                    submission_state="accepted",
                    issues=[],
                )
            )
        else:
            incomplete_count += 1
            # Check if there are conflict/duplicate records for this participant.
            p_records = [
                c for c in all_contributions if c.participant_id == p.id
            ]
            has_conflict = any(c.status == "conflict" for c in p_records)
            has_duplicate = any(c.status == "duplicate" for c in p_records)

            if has_conflict:
                state = "conflict"
                issue = (
                    f"Participant '{p.name}' has conflicting submissions but "
                    f"no accepted canonical contribution."
                )
            elif has_duplicate:
                state = "duplicate"
                issue = (
                    f"Participant '{p.name}' has duplicate submissions but "
                    f"no accepted canonical contribution."
                )
            elif ceremony.status == "recovering":
                state = "recovering"
                issue = (
                    f"Participant '{p.name}' has not submitted during recovery."
                )
            else:
                state = "missing"
                issue = (
                    f"Participant '{p.name}' has not submitted a contribution."
                )
            issues.append(issue)
            participant_statuses.append(
                ParticipantMonitorStatus(
                    participant_id=p.id,
                    participant_name=p.name,
                    has_canonical=False,
                    submission_state=state,
                    issues=[issue],
                )
            )

    # Determine overall monitor status.
    total = len(participants)
    complete = total - incomplete_count

    if total == 0:
        monitor_status = "not_ready"
        message = "No participants have been added to this ceremony."
    elif verified is False:
        monitor_status = "verification_failed"
        message = (
            "Final verification failed: the canonical contribution set has "
            "changed since finalization."
        )
        issues.append("Final verification failed.")
    elif incomplete_count > 0 and conflict_count > 0:
        monitor_status = "conflict_requires_attention"
        message = (
            f"{incomplete_count} participant(s) missing contributions and "
            f"{conflict_count} conflict(s) detected. Manual review required."
        )
    elif conflict_count > 0 and incomplete_count == 0:
        monitor_status = "healthy"
        message = (
            "All participants have canonical contributions. Conflict records "
            "exist but do not affect the canonical set."
        )
    elif ceremony.status == "recovering":
        monitor_status = "recovering"
        message = (
            f"Ceremony is in recovery. {incomplete_count} participant(s) "
            f"still need to submit."
        )
    elif incomplete_count > 0:
        monitor_status = "incomplete"
        message = (
            f"{incomplete_count} of {total} participant(s) have not yet "
            f"submitted contributions."
        )
    elif has_final_result and verified:
        monitor_status = "healthy"
        message = (
            "All participants have canonical contributions and the final "
            "result is verified."
        )
    else:
        monitor_status = "healthy"
        message = (
            "All participants have canonical contributions. Ready for "
            "finalization."
        )

    return CeremonyMonitorResponse(
        ceremony_id=ceremony_id,
        ceremony_name=ceremony.name,
        ceremony_status=ceremony.status,
        monitor_status=monitor_status,
        total_participants=total,
        participants_with_contribution=complete,
        incomplete_count=incomplete_count,
        conflict_count=conflict_count,
        duplicate_count=duplicate_count,
        has_final_result=has_final_result,
        verified=verified,
        participants=participant_statuses,
        issues=issues,
        message=message,
    )


# --------------------------------------------------------------------------- #
# Recovery report
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RecoveryReportResult:
    """Internal result of a recovery report generation."""

    response: RecoveryReportResponse
    audit_events: list[str]


def generate_recovery_report(
    db: Session,
    ceremony_id: int,
    request: RecoveryReportRequest,
) -> RecoveryReportResult:
    """Generate an incident/recovery report for a participant.

    This function assesses the state of a participant's submission and
    determines whether automatic recovery is safe.  It records audit events
    for the recovery process.

    If ``request.submission_key`` is provided, the system checks whether that
    logical submission already exists.  If it does and is accepted, the report
    confirms the existing contribution without creating a new one.

    If ``request.contribution_data`` is provided and no existing submission is
    found, the system attempts a safe retry using the same submission key.
    """
    ceremony = ceremony_service.get_ceremony(db, ceremony_id)
    if ceremony is None:
        raise LookupError("Ceremony not found")

    participant = participant_service.get_participant(db, request.participant_id)
    if participant is None:
        raise LookupError("Participant not found")
    if participant.ceremony_id != ceremony_id:
        raise ValueError("Participant does not belong to the specified ceremony")

    audit_events: list[str] = []

    record_event(
        db,
        ceremony_id=ceremony_id,
        participant_id=request.participant_id,
        event_type="SUBMISSION_RECOVERY_STARTED",
        message=(
            f"Recovery report initiated for participant '{participant.name}' "
            f"(id={request.participant_id}) in ceremony {ceremony_id}."
        ),
    )
    audit_events.append("SUBMISSION_RECOVERY_STARTED")

    # --- Step 1: Check for an existing canonical contribution ---
    canonical = contribution_service._find_canonical(
        db, ceremony_id, request.participant_id
    )

    # --- Step 2: If a submission_key is provided, check its status ---
    submission_status_str = "UNKNOWN"
    existing_record = None
    if request.submission_key:
        record_event(
            db,
            ceremony_id=ceremony_id,
            participant_id=request.participant_id,
            event_type="SUBMISSION_STATUS_CHECKED",
            message=(
                f"Checking submission status for key '{request.submission_key}' "
                f"(participant {request.participant_id})."
            ),
        )
        audit_events.append("SUBMISSION_STATUS_CHECKED")

        status, contrib, record = contribution_service.get_submission_status(
            db, ceremony_id, request.submission_key
        )
        submission_status_str = status
        existing_record = record

        if status == "ACCEPTED" and contrib is not None:
            # The submission was already accepted. Confirm it.
            record_event(
                db,
                ceremony_id=ceremony_id,
                participant_id=request.participant_id,
                event_type="SUBMISSION_ALREADY_ACCEPTED",
                message=(
                    f"Submission '{request.submission_key}' already accepted "
                    f"(contribution id={contrib.id}). No new contribution created."
                ),
            )
            audit_events.append("SUBMISSION_ALREADY_ACCEPTED")
            db.commit()

            canonical_set = get_canonical_set(db, ceremony_id)
            ready = len(canonical_set.contributions) == len(
                canonical_set.participants
            )

            return RecoveryReportResult(
                response=RecoveryReportResponse(
                    ceremony_id=ceremony_id,
                    ceremony_name=ceremony.name,
                    participant_id=request.participant_id,
                    participant_name=participant.name,
                    attempt_id=record.attempt_id if record else None,
                    issue="Submission confirmation was not received.",
                    detected_state="Existing contribution found and accepted.",
                    automatic_action=(
                        "Checked logical submission identifier. Confirmed "
                        "existing accepted contribution."
                    ),
                    recovery_status="recovered",
                    duplicate_created=False,
                    canonical_contribution_changed=False,
                    ceremony_ready=ready,
                    contribution_id=contrib.id,
                    contribution_hash=contrib.contribution_hash,
                    manual_steps=[],
                    message=(
                        "Existing contribution confirmed as ACCEPTED. No "
                        "duplicate created. Ceremony can continue."
                    ),
                ),
                audit_events=audit_events,
            )

    # --- Step 3: If canonical exists but submission key not found ---
    # If the participant has a canonical contribution AND no retry data is
    # provided, confirm the existing contribution.  If retry data IS provided
    # (contribution_data + submission_key), fall through to Step 4 to attempt
    # the retry — this allows conflict detection when different data is submitted.
    if canonical is not None and not (
        request.contribution_data and request.submission_key
    ):
        # The participant already has a canonical contribution, but the
        # specific submission key was not found (or no key was provided).
        # The canonical contribution exists and is safe.
        record_event(
            db,
            ceremony_id=ceremony_id,
            participant_id=request.participant_id,
            event_type="SUBMISSION_ALREADY_ACCEPTED",
            message=(
                f"Canonical contribution {canonical.id} already exists for "
                f"participant '{participant.name}'. No recovery needed."
            ),
        )
        audit_events.append("SUBMISSION_ALREADY_ACCEPTED")
        db.commit()

        canonical_set = get_canonical_set(db, ceremony_id)
        ready = len(canonical_set.contributions) == len(
            canonical_set.participants
        )

        return RecoveryReportResult(
            response=RecoveryReportResponse(
                ceremony_id=ceremony_id,
                ceremony_name=ceremony.name,
                participant_id=request.participant_id,
                participant_name=participant.name,
                attempt_id=canonical.attempt_id,
                issue="Submission confirmation was not received.",
                detected_state=(
                    f"Existing canonical contribution found (id={canonical.id})."
                ),
                automatic_action=(
                    "Confirmed existing canonical contribution. No new "
                    "contribution created."
                ),
                recovery_status="recovered",
                duplicate_created=False,
                canonical_contribution_changed=False,
                ceremony_ready=ready,
                contribution_id=canonical.id,
                contribution_hash=canonical.contribution_hash,
                manual_steps=[],
                message=(
                    "Existing canonical contribution confirmed. No duplicate "
                    "created. Ceremony can continue."
                ),
            ),
            audit_events=audit_events,
        )

    # --- Step 4: Attempt a safe retry if contribution_data + submission_key ---
    # This handles two cases:
    #   (a) No canonical contribution exists — retry creates a new one.
    #   (b) Canonical exists but the user provided different data — retry
    #       triggers conflict detection, which is reported as unrecoverable.
    if request.contribution_data and request.submission_key:
        # Safe retry: submit with the same submission key.
        from app.schemas import ContributionCreate
        from app.services import attempts as attempt_service

        attempts = attempt_service.list_attempts_for_ceremony(db, ceremony_id)
        if not attempts:
            # No attempt exists — cannot retry safely.
            return _build_unrecoverable_report(
                db,
                ceremony_id=ceremony_id,
                ceremony_name=ceremony.name,
                participant_id=request.participant_id,
                participant_name=participant.name,
                issue="No ceremony attempt exists for submission.",
                detected_state="No attempt available for safe retry.",
                audit_events=audit_events,
            )

        latest_attempt = attempts[-1]
        payload = ContributionCreate(
            participant_id=request.participant_id,
            contribution_data=request.contribution_data,
            submission_key=request.submission_key,
        )

        result = contribution_service.submit_contribution(
            db,
            ceremony_id=ceremony_id,
            attempt_id=latest_attempt.id,
            payload=payload,
        )

        if result.status == "accepted":
            record_event(
                db,
                ceremony_id=ceremony_id,
                participant_id=request.participant_id,
                event_type="SUBMISSION_RETRY_ACCEPTED",
                message=(
                    f"Safe retry of submission '{request.submission_key}' "
                    f"succeeded. Contribution {result.canonical.id} accepted."
                ),
            )
            audit_events.append("SUBMISSION_RETRY_ACCEPTED")
            db.commit()

            canonical_set = get_canonical_set(db, ceremony_id)
            ready = len(canonical_set.contributions) == len(
                canonical_set.participants
            )

            return RecoveryReportResult(
                response=RecoveryReportResponse(
                    ceremony_id=ceremony_id,
                    ceremony_name=ceremony.name,
                    participant_id=request.participant_id,
                    participant_name=participant.name,
                    attempt_id=latest_attempt.id,
                    issue="Submission was not received by the server.",
                    detected_state="No existing contribution found.",
                    automatic_action=(
                        "Safely retried the same logical submission. New "
                        "contribution accepted."
                    ),
                    recovery_status="recovered",
                    duplicate_created=False,
                    canonical_contribution_changed=False,
                    ceremony_ready=ready,
                    contribution_id=result.canonical.id,
                    contribution_hash=result.canonical.contribution_hash,
                    manual_steps=[],
                    message=(
                        "Contribution accepted after safe retry. No duplicate "
                        "created."
                    ),
                ),
                audit_events=audit_events,
            )
        elif result.status == "duplicate":
            # The retry matched an existing contribution — safe.
            record_event(
                db,
                ceremony_id=ceremony_id,
                participant_id=request.participant_id,
                event_type="SUBMISSION_ALREADY_ACCEPTED",
                message=(
                    f"Safe retry of submission '{request.submission_key}' "
                    f"matched existing contribution {result.canonical.id}."
                ),
            )
            audit_events.append("SUBMISSION_ALREADY_ACCEPTED")
            db.commit()

            canonical_set = get_canonical_set(db, ceremony_id)
            ready = len(canonical_set.contributions) == len(
                canonical_set.participants
            )

            return RecoveryReportResult(
                response=RecoveryReportResponse(
                    ceremony_id=ceremony_id,
                    ceremony_name=ceremony.name,
                    participant_id=request.participant_id,
                    participant_name=participant.name,
                    attempt_id=latest_attempt.id,
                    issue="Submission confirmation was not received.",
                    detected_state="Existing contribution matched on retry.",
                    automatic_action=(
                        "Safe retry matched existing contribution. No new "
                        "canonical contribution created."
                    ),
                    recovery_status="recovered",
                    duplicate_created=True,
                    canonical_contribution_changed=False,
                    ceremony_ready=ready,
                    contribution_id=result.canonical.id,
                    contribution_hash=result.canonical.contribution_hash,
                    manual_steps=[],
                    message=(
                        "Existing contribution confirmed via safe retry."
                    ),
                ),
                audit_events=audit_events,
            )
        elif result.status == "conflict":
            # Conflict: different data. Cannot auto-resolve.
            return _build_unrecoverable_report(
                db,
                ceremony_id=ceremony_id,
                ceremony_name=ceremony.name,
                participant_id=request.participant_id,
                participant_name=participant.name,
                issue=(
                    "Conflicting contribution detected during retry. "
                    "The original contribution was preserved."
                ),
                detected_state=(
                    f"Conflict: submitted hash differs from canonical "
                    f"({result.canonical.contribution_hash[:16]}...)."
                ),
                audit_events=audit_events,
            )

    # --- Step 5: Cannot safely determine state ---
    return _build_unrecoverable_report(
        db,
        ceremony_id=ceremony_id,
        ceremony_name=ceremony.name,
        participant_id=request.participant_id,
        participant_name=participant.name,
        issue=(
            "Contribution state could not be safely determined. "
            "No submission key or contribution data provided for retry."
        ),
        detected_state="No existing contribution and no retry data available.",
        audit_events=audit_events,
    )


def _build_unrecoverable_report(
    db: Session,
    *,
    ceremony_id: int,
    ceremony_name: str,
    participant_id: int,
    participant_name: str,
    issue: str,
    detected_state: str,
    audit_events: list[str],
) -> RecoveryReportResult:
    """Build a report for an unrecoverable situation and record audit events."""
    record_event(
        db,
        ceremony_id=ceremony_id,
        participant_id=participant_id,
        event_type="SUBMISSION_RECOVERY_FAILED",
        message=(
            f"Automatic recovery failed for participant '{participant_name}' "
            f"in ceremony {ceremony_id}. Issue: {issue}"
        ),
    )
    audit_events.append("SUBMISSION_RECOVERY_FAILED")

    record_event(
        db,
        ceremony_id=ceremony_id,
        participant_id=participant_id,
        event_type="MANUAL_ACTION_REQUIRED",
        message=(
            f"Manual action required for participant '{participant_name}' "
            f"in ceremony {ceremony_id}."
        ),
    )
    audit_events.append("MANUAL_ACTION_REQUIRED")
    db.commit()

    canonical_set = get_canonical_set(db, ceremony_id)
    ready = len(canonical_set.contributions) == len(canonical_set.participants)

    manual_steps = [
        "1. Verify participant identity.",
        "2. Check ceremony status.",
        "3. Check whether a canonical contribution exists for this participant.",
        "4. Resume the participant's ceremony attempt.",
        "5. Submit only if no canonical contribution exists.",
        "6. Run final verification.",
    ]

    return RecoveryReportResult(
        response=RecoveryReportResponse(
            ceremony_id=ceremony_id,
            ceremony_name=ceremony_name,
            participant_id=participant_id,
            participant_name=participant_name,
            attempt_id=None,
            issue=issue,
            detected_state=detected_state,
            automatic_action="Automatic recovery was not safe. Stopped.",
            recovery_status="not_safe",
            duplicate_created=False,
            canonical_contribution_changed=False,
            ceremony_ready=ready,
            contribution_id=None,
            contribution_hash=None,
            manual_steps=manual_steps,
            message=(
                "Automatic recovery could not safely determine the "
                "submission state. Manual action required. Ceremony remains "
                f"{'READY' if ready else 'INCOMPLETE / NOT VERIFIED'}."
            ),
        ),
        audit_events=audit_events,
    )
