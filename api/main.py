"""Backward-compatible Vercel entry when deployments still route to api/main.py."""

from main import app

__all__ = ["app"]
