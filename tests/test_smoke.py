"""Smoke tests for repository layout and import health."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SmokeTests(unittest.TestCase):
    def test_key_modules_import(self):
        import app.main  # noqa: F401
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

    def test_vercel_entry_imports(self):
        import importlib.util

        index_path = ROOT / "main.py"
        spec = importlib.util.spec_from_file_location("vercel_main", index_path)
        module = importlib.util.module_from_spec(spec)
        self.assertIsNotNone(spec.loader)
        spec.loader.exec_module(module)
        self.assertTrue(hasattr(module, "app"))

    def test_streamlit_dashboard_exists(self):
        self.assertTrue((ROOT / "dashboard" / "app.py").exists())

    def test_gitignore_excludes_local_env(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".venv/", gitignore)
        self.assertIn("*.egg-info/", gitignore)

    def test_serverless_database_url_uses_tmp(self):
        import os

        import pipeline.db as db

        db.reset_db_connections()
        with self.subTest(env="VERCEL"):
            os.environ["VERCEL"] = "1"
            self.assertTrue(db.is_serverless_runtime())
            url = db.get_database_url()
            self.assertEqual(url, db.SERVERLESS_SQLITE_URL)
        db.reset_db_connections()
        os.environ.pop("VERCEL", None)

    def test_demo_seed_database_is_tracked(self):
        self.assertTrue((ROOT / "data" / "leasepulse.db").exists())


if __name__ == "__main__":
    unittest.main()
