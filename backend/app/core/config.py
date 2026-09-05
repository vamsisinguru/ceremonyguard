"""Application configuration.

Configuration is loaded from environment variables with sensible defaults
so the project runs out-of-the-box in development while remaining
overridable in other environments.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the CeremonyGuard backend."""

    app_name: str = _env("APP_NAME", "CeremonyGuard")
    environment: str = _env("ENVIRONMENT", "development")
    # SQLite database URL. Defaults to a local file in the backend directory.
    database_url: str = _env("DATABASE_URL", "sqlite:///./ceremonyguard.db")
    # Echo SQL statements only in development.
    db_echo: bool = _env("DB_ECHO", "false").lower() == "true"


settings = Settings()
