"""Smart Ceremony Monitoring & Automatic Recovery REST API.

Endpoints:

- ``GET  /ceremonies/{ceremony_id}/monitor`` — overall ceremony monitoring status.
- ``GET  /ceremonies/{ceremony_id}/submissions/{submission_key}/status`` —
  submission status lookup by idempotency key.
- ``POST /ceremonies/{ceremony_id}/recovery/report`` — generate an
  incident/recovery report for a participant.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import (
    CeremonyMonitorResponse,
    RecoveryReportRequest,
    RecoveryReportResponse,
    SubmissionStatusResponse,
)
from app.services import ceremonies as ceremony_service
from app.services import monitoring as monitoring_service

router = APIRouter(tags=["monitoring"])


@router.get(
    "/ceremonies/{ceremony_id}/monitor",
    response_model=CeremonyMonitorResponse,
    summary="Get ceremony monitoring status",
)
def get_ceremony_monitor(
    ceremony_id: int, db: Session = Depends(get_db)
) -> CeremonyMonitorResponse:
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")
    try:
        return monitoring_service.get_ceremony_monitor(db, ceremony_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/ceremonies/{ceremony_id}/submissions/{submission_key}/status",
    response_model=SubmissionStatusResponse,
    summary="Check submission status by idempotency key",
)
def get_submission_status(
    ceremony_id: int,
    submission_key: str,
    db: Session = Depends(get_db),
) -> SubmissionStatusResponse:
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")
    try:
        return monitoring_service.get_submission_status_response(
            db, ceremony_id, submission_key
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/ceremonies/{ceremony_id}/recovery/report",
    response_model=RecoveryReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a recovery/incident report for a participant",
)
def generate_recovery_report(
    ceremony_id: int,
    payload: RecoveryReportRequest,
    db: Session = Depends(get_db),
) -> RecoveryReportResponse:
    if ceremony_service.get_ceremony(db, ceremony_id) is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")
    try:
        result = monitoring_service.generate_recovery_report(
            db, ceremony_id, payload
        )
        return result.response
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
