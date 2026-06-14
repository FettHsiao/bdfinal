"""Vercel FastAPI entrypoint (see pyproject.toml [tool.vercel])."""

from app.main import app

__all__ = ["app"]
