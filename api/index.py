"""Vercel serverless entrypoint for the LeasePulse FastAPI app."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TMP_DB = Path("/tmp/leasepulse.db")
SEED_DB = ROOT / "data" / "leasepulse.db"

if SEED_DB.exists() and not TMP_DB.exists():
    shutil.copyfile(SEED_DB, TMP_DB)

os.environ.setdefault("DATABASE_URL", f"sqlite:///{TMP_DB}")
os.environ.setdefault("ALLOW_REPROCESS", "false")

from app.main import app
