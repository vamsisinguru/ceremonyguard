"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    """Return service health, including a live database connectivity check."""
    db.execute(text("SELECT 1"))
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
    )
