"""Smoke tests for repository layout and import health."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SmokeTests(unittest.TestCase):
    def test_key_modules_import(self):
        import api.main  # noqa: F401
        import data.collect_public_demand_evidence  # noqa: F401
        import data.collect_search_trends  # noqa: F401
        import data.ingest  # noqa: F401
        import data.taipei_open_data  # noqa: F401
        import pipeline.processor  # noqa: F401

    def test_data_collectors_live_under_data_package(self):
        self.assertTrue((ROOT / "data/collect_ptt_forum_signals.py").exists())
        self.assertTrue((ROOT / "data/collect_search_trends.py").exists())
        self.assertTrue((ROOT / "data/collect_app_store_reviews.py").exists())
        self.assertTrue((ROOT / "data/collect_competitor_pricing.py").exists())
        self.assertTrue((ROOT / "data/collect_public_demand_evidence.py").exists())
        self.assertTrue((ROOT / "data/sources/competitor_pricing_sources.json").exists())

    def test_scripts_are_thin_wrappers(self):
        wrapper = (ROOT / "scripts/collect_search_trends.py").read_text(encoding="utf-8")
        self.assertIn("from data.collect_search_trends import main", wrapper)
        self.assertLess(len(wrapper.splitlines()), 10)

    def test_gitignore_excludes_local_env(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".venv/", gitignore)
        self.assertIn("*.egg-info/", gitignore)


if __name__ == "__main__":
    unittest.main()
