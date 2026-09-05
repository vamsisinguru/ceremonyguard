"""FastAPI application entrypoint for CeremonyGuard."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup. In later phases this will be replaced by
    # proper migrations (e.g. Alembic).
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Multi-Party Ceremony Consistency System",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)


@app.get("/")
def root() -> dict[str, str]:
    """Root informational endpoint."""
    return {"name": settings.app_name, "phase": "1"}
