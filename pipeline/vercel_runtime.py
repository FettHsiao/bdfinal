"""Runtime bootstrap for Vercel / serverless deployments."""

from __future__ import annotations

from pathlib import Path

from pipeline.db import ensure_serverless_sqlite, reset_db_connections


def configure_vercel_sqlite(root: Path | None = None) -> None:
    """Ensure serverless runtimes use /tmp SQLite before importing the FastAPI app."""
    del root  # seed lookup is centralized in pipeline.db
    ensure_serverless_sqlite()
    reset_db_connections()
