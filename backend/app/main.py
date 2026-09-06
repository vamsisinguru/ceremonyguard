"""FastAPI application entrypoint for CeremonyGuard."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.attempts import router as attempts_router
from app.api.audit import router as audit_router
from app.api.ceremonies import router as ceremonies_router
from app.api.contributions import router as contributions_router
from app.api.health import router as health_router
from app.api.monitoring import router as monitoring_router
from app.api.participants import router as participants_router
from app.api.recovery import router as recovery_router
from app.api.verification import router as verification_router
from app.core.config import settings
from app.core.database import init_db

# Path to the built React frontend (frontend/dist/).
# In tests this directory may not exist; we guard all frontend-serving logic
# behind an existence check so the API-only behaviour is preserved.
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
_FRONTEND_INDEX = FRONTEND_DIST / "index.html"
_FRONTEND_ASSETS = FRONTEND_DIST / "assets"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup. In later phases this will be replaced by
    # proper migrations (e.g. Alembic).
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Multi-Party Ceremony Consistency System",
    version="0.4.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(ceremonies_router)
app.include_router(participants_router)
app.include_router(attempts_router)
app.include_router(contributions_router)
app.include_router(audit_router)
app.include_router(recovery_router)
app.include_router(verification_router)
app.include_router(monitoring_router)

# Mount static frontend assets (JS/CSS) if the build exists.
if _FRONTEND_ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_ASSETS)), name="assets")


@app.get("/")
def root(request: Request):
    """Root endpoint.

    Uses content negotiation: browsers (Accept: text/html) receive the React
    frontend; API clients and tests receive a JSON info payload.
    """
    accept = request.headers.get("accept", "")
    if "text/html" in accept and _FRONTEND_INDEX.is_file():
        return FileResponse(str(_FRONTEND_INDEX))
    return {"name": settings.app_name, "phase": "4"}


# SPA fallback — must be registered *after* all API routers so that API routes
# are matched first.  Serves index.html for non-API paths requested by browsers.
@app.get("/{full_path:path}")
def spa_fallback(full_path: str, request: Request):
    # Never intercept FastAPI's built-in docs / schema endpoints.
    if full_path in ("docs", "redoc", "openapi.json"):
        raise HTTPException(status_code=404)

    # If the path maps to an actual file in the dist directory, serve it.
    candidate = FRONTEND_DIST / full_path
    if candidate.is_file():
        return FileResponse(str(candidate))

    # SPA fallback: return index.html for browser navigation requests.
    accept = request.headers.get("accept", "")
    if "text/html" in accept and _FRONTEND_INDEX.is_file():
        return FileResponse(str(_FRONTEND_INDEX))

    raise HTTPException(status_code=404)
