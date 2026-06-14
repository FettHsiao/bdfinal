"""Runtime bootstrap for Vercel / serverless deployments."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def configure_vercel_sqlite(root: Path | None = None) -> None:
    """Copy seed SQLite to /tmp and force DATABASE_URL on Vercel."""
    if not os.getenv("VERCEL"):
        return

    root = root or Path(__file__).resolve().parents[1]
    tmp_db = Path("/tmp/leasepulse.db")
    seed_db = root / "data" / "leasepulse.db"

    if seed_db.exists() and not tmp_db.exists():
        shutil.copyfile(seed_db, tmp_db)

    # Force override: Vercel dashboard env may point at data/leasepulse.db (read-only).
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db}"
    os.environ["ALLOW_REPROCESS"] = "false"
