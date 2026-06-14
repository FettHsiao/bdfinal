"""Shared project paths for data acquisition modules."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data/raw"
PROCESSED_DIR = ROOT / "data/processed"
SOURCES_DIR = ROOT / "data/sources"
