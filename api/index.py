"""Legacy Vercel entry; prefer root main.py via [tool.vercel]."""

from main import app

__all__ = ["app"]
