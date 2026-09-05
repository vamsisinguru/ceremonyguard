"""Audit event service.

Records immutable audit trail entries for important ceremony operations.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditEvent


def record_event(
    db: Session,
    *,
    ceremony_id: int,
    event_type: str,
    message: str,
    participant_id: int | None = None,
) -> AuditEvent:
    """Create and persist an AuditEvent. Caller is responsible for commit."""
    event = AuditEvent(
        ceremony_id=ceremony_id,
        participant_id=participant_id,
        event_type=event_type,
        message=message,
    )
    db.add(event)
    db.flush()
    return event
