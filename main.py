"""Vercel FastAPI entrypoint (see pyproject.toml [tool.vercel])."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.vercel_runtime import configure_vercel_sqlite

configure_vercel_sqlite(ROOT)

from app.main import app
