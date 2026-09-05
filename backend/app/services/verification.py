"""Final result generation and cryptographic verification (Phase 4).

This is a **simulated** educational ceremony. The final result is a
deterministic HMAC-SHA256 digest computed over the set of canonical
(accepted) contributions.  It is **not** a real threshold signature.

Generation:
    1. Collect all canonical accepted contributions for the ceremony,
       ordered by participant ID.
    2. Build a deterministic message from each contribution's
       (contribution_id, participant_id, contribution_hash).
    3. Compute a SHA-256 digest of the ordered contribution hashes
       (``contribution_digest``) for traceability.
    4. Compute an HMAC-SHA256 of the full message using a ceremony-derived
       key (``final_digest``).
    5. Persist the result in ``CeremonyResult``.

Verification:
    1. Recompute ``contribution_digest`` and ``final_digest`` from the
       *current* canonical contributions.
    2. Compare against the stored values.
    3. If they match, the canonical contribution set is unchanged since
       finalization.  If they differ, a contribution was modified, removed,
       or replaced.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CeremonyResult, Contribution, Participant
from app.services.audit import record_event
from app.services.contributions import STATUS_ACCEPTED

# A fixed application-level secret used for the simulated HMAC key.
# In a real system this would be managed via a proper key management service.
_SIMULATED_SECRET = b"ceremonyguard-simulated-final-result-key"


def _derive_ceremony_key(ceremony_id: int) -> bytes:
    """Derive a deterministic HMAC key for a ceremony."""
    return hashlib.sha256(
        _SIMULATED_SECRET + str(ceremony_id).encode("utf-8")
    ).digest()


def _build_contribution_digest(contributions: list[Contribution]) -> str:
    """SHA-256 of the ordered canonical contribution hashes."""
    ordered = sorted(contributions, key=lambda c: c.participant_id)
    parts = [c.contribution_hash for c in ordered]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _build_final_message(contributions: list[Contribution]) -> bytes:
    """Deterministic message from the canonical contribution set."""
    ordered = sorted(contributions, key=lambda c: c.participant_id)
    parts = [
        f"{c.id}:{c.participant_id}:{c.contribution_hash}" for c in ordered
    ]
    return "|".join(parts).encode("utf-8")


def _compute_final_digest(ceremony_id: int, contributions: list[Contribution]) -> str:
    """HMAC-SHA256 of the contribution set using a ceremony-derived key."""
    from cryptography.hazmat.primitives import hashes, hmac

    key = _derive_ceremony_key(ceremony_id)
    message = _build_final_message(contributions)
    h = hmac.HMAC(key, hashes.SHA256())
    h.update(message)
    return h.finalize().hex()


@dataclass(frozen=True)
class CanonicalSet:
    """The canonical contribution set for a ceremony."""

    contributions: list[Contribution]
    participants: list[Participant]


def get_canonical_set(db: Session, ceremony_id: int) -> CanonicalSet:
    """Return all canonical accepted contributions and participants for a ceremony."""
    contributions = list(
        db.scalars(
            select(Contribution)
            .where(
                Contribution.ceremony_id == ceremony_id,
                Contribution.status == STATUS_ACCEPTED,
            )
            .order_by(Contribution.participant_id)
        )
    )
    participants = list(
        db.scalars(
            select(Participant)
            .where(Participant.ceremony_id == ceremony_id)
            .order_by(Participant.id)
        )
    )
    return CanonicalSet(contributions=contributions, participants=participants)


def is_ceremony_ready(db: Session, ceremony_id: int) -> bool:
    """A ceremony is ready when every participant has exactly one canonical contribution."""
    canonical_set = get_canonical_set(db, ceremony_id)
    if len(canonical_set.participants) == 0:
        return False
    if len(canonical_set.contributions) != len(canonical_set.participants):
        return False
    participant_ids = {p.id for p in canonical_set.participants}
    contributed_ids = {c.participant_id for c in canonical_set.contributions}
    return participant_ids == contributed_ids


def generate_final_result(db: Session, ceremony_id: int) -> CeremonyResult:
    """Generate and persist the final result for a ceremony.

    Raises ``ValueError`` if the ceremony is not ready (i.e. not all
    participants have canonical contributions).
    """
    if not is_ceremony_ready(db, ceremony_id):
        raise ValueError("Ceremony is not ready: not all participants have canonical contributions.")

    canonical_set = get_canonical_set(db, ceremony_id)
    contribution_digest = _build_contribution_digest(canonical_set.contributions)
    final_digest = _compute_final_digest(ceremony_id, canonical_set.contributions)

    # Replace any existing result (re-finalization).
    existing = db.scalar(
        select(CeremonyResult).where(CeremonyResult.ceremony_id == ceremony_id)
    )
    if existing is not None:
        db.delete(existing)
        db.flush()

    result = CeremonyResult(
        ceremony_id=ceremony_id,
        final_digest=final_digest,
        contribution_digest=contribution_digest,
        participant_count=len(canonical_set.contributions),
    )
    db.add(result)
    db.flush()

    record_event(
        db,
        ceremony_id=ceremony_id,
        event_type="FINAL_RESULT_GENERATED",
        message=(
            f"Final result generated for ceremony {ceremony_id} "
            f"with {len(canonical_set.contributions)} canonical contributions "
            f"(digest={final_digest[:16]}...)."
        ),
    )
    db.commit()
    db.refresh(result)
    return result


def verify_final_result(db: Session, ceremony_id: int) -> tuple[bool, str]:
    """Verify the stored final result against the current canonical contributions.

    Returns ``(verified, message)``.  If no result has been generated,
    returns ``(False, "not_generated")``.
    """
    stored = db.scalar(
        select(CeremonyResult).where(CeremonyResult.ceremony_id == ceremony_id)
    )
    if stored is None:
        return False, "Final result has not been generated yet."

    canonical_set = get_canonical_set(db, ceremony_id)
    current_contribution_digest = _build_contribution_digest(canonical_set.contributions)
    current_final_digest = _compute_final_digest(ceremony_id, canonical_set.contributions)

    if current_contribution_digest != stored.contribution_digest:
        record_event(
            db,
            ceremony_id=ceremony_id,
            event_type="FINAL_RESULT_VERIFICATION_FAILED",
            message=(
                f"Final result verification FAILED for ceremony {ceremony_id}: "
                f"contribution digest mismatch "
                f"(stored={stored.contribution_digest[:16]}..., "
                f"current={current_contribution_digest[:16]}...)."
            ),
        )
        db.commit()
        return False, "Verification failed: contribution set has changed since finalization."

    if current_final_digest != stored.final_digest:
        record_event(
            db,
            ceremony_id=ceremony_id,
            event_type="FINAL_RESULT_VERIFICATION_FAILED",
            message=(
                f"Final result verification FAILED for ceremony {ceremony_id}: "
                f"final digest mismatch."
            ),
        )
        db.commit()
        return False, "Verification failed: final digest mismatch."

    record_event(
        db,
        ceremony_id=ceremony_id,
        event_type="FINAL_RESULT_VERIFIED",
        message=(
            f"Final result verification SUCCEEDED for ceremony {ceremony_id} "
            f"(digest={stored.final_digest[:16]}...)."
        ),
    )
    db.commit()
    return True, "Verification succeeded: canonical contribution set is unchanged."


def get_stored_result(db: Session, ceremony_id: int) -> CeremonyResult | None:
    """Return the stored final result for a ceremony, if any."""
    return db.scalar(
        select(CeremonyResult).where(CeremonyResult.ceremony_id == ceremony_id)
    )
