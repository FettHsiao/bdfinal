"""Taipei open-data acquisition and public demand-evidence collectors."""

from data.collect_app_store_reviews import main as collect_app_store_reviews
from data.collect_competitor_pricing import main as collect_competitor_pricing
from data.collect_ptt_forum_signals import crawl_forum_signals, main as collect_ptt_forum_signals
from data.collect_public_demand_evidence import main as collect_public_demand_evidence
from data.collect_search_trends import main as collect_search_trends
from data.ingest import fetch_and_ingest, ingest_csv, main as ingest_main
from data.taipei_open_data import (
    INGEST_CSV_PATH,
    RENT_CSV_PATH,
    SUMMARY_CSV_PATH,
    TAIPEI_REAL_PRICE_WEEKLY_CSV_URL,
    fetch_and_process,
    main as fetch_main,
)

__all__ = [
    "INGEST_CSV_PATH",
    "RENT_CSV_PATH",
    "SUMMARY_CSV_PATH",
    "TAIPEI_REAL_PRICE_WEEKLY_CSV_URL",
    "collect_app_store_reviews",
    "collect_competitor_pricing",
    "collect_ptt_forum_signals",
    "collect_public_demand_evidence",
    "collect_search_trends",
    "crawl_forum_signals",
    "fetch_and_ingest",
    "fetch_and_process",
    "fetch_main",
    "ingest_csv",
    "ingest_main",
]
