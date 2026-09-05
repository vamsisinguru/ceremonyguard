"""Audit event REST API — read-only audit trail access."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AuditEvent
from app.schemas import AuditEventResponse
from app.services import ceremonies as ceremony_service

router = APIRouter(tags=["audit"])


@router.get(
    "/ceremonies/{ceremony_id}/audit",
    response_model=list[AuditEventResponse],
    summary="List audit events for a ceremony",
)
def list_audit_events(
    ceremony_id: int, db: Session = Depends(get_db)
) -> list[AuditEventResponse]:
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.ceremony_id == ceremony_id)
            .order_by(AuditEvent.id)
        )
    )
    return [AuditEventResponse.model_validate(e) for e in events]
