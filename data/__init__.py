"""Taipei open-data acquisition package."""

from data.taipei_open_data import (
    INGEST_CSV_PATH,
    RENT_CSV_PATH,
    SUMMARY_CSV_PATH,
    TAIPEI_REAL_PRICE_WEEKLY_CSV_URL,
    fetch_and_process,
    main,
)

__all__ = [
    "INGEST_CSV_PATH",
    "RENT_CSV_PATH",
    "SUMMARY_CSV_PATH",
    "TAIPEI_REAL_PRICE_WEEKLY_CSV_URL",
    "fetch_and_process",
    "main",
]
