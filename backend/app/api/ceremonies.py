"""Ceremony REST API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import (
    CeremonyCreate,
    CeremonyResponse,
    CeremonyStatusUpdate,
)
from app.services import ceremonies as ceremony_service

router = APIRouter(prefix="/ceremonies", tags=["ceremonies"])


@router.post(
    "",
    response_model=CeremonyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a ceremony",
)
def create_ceremony(
    payload: CeremonyCreate, db: Session = Depends(get_db)
) -> CeremonyResponse:
    ceremony = ceremony_service.create_ceremony(db, payload)
    return CeremonyResponse.model_validate(ceremony)


@router.get(
    "",
    response_model=list[CeremonyResponse],
    summary="List ceremonies",
)
def list_ceremonies(db: Session = Depends(get_db)) -> list[CeremonyResponse]:
    return [CeremonyResponse.model_validate(c) for c in ceremony_service.list_ceremonies(db)]


@router.get(
    "/{ceremony_id}",
    response_model=CeremonyResponse,
    summary="Retrieve a ceremony by ID",
)
def get_ceremony(ceremony_id: int, db: Session = Depends(get_db)) -> CeremonyResponse:
    ceremony = ceremony_service.get_ceremony(db, ceremony_id)
    if ceremony is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")
    return CeremonyResponse.model_validate(ceremony)


@router.patch(
    "/{ceremony_id}/status",
    response_model=CeremonyResponse,
    summary="Update a ceremony's status",
)
def update_ceremony_status(
    ceremony_id: int,
    payload: CeremonyStatusUpdate,
    db: Session = Depends(get_db),
) -> CeremonyResponse:
    ceremony = ceremony_service.get_ceremony(db, ceremony_id)
    if ceremony is None:
        raise HTTPException(status_code=404, detail="Ceremony not found")
    updated = ceremony_service.update_ceremony_status(db, ceremony, payload)
    return CeremonyResponse.model_validate(updated)
