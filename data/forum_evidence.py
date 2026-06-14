"""Shared helpers for forum-based demand evidence."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FORUM_REAL_PATH = ROOT / "data/processed/forum_signals_real.json"


def resolve_forum_path(preferred: Path | None = None) -> tuple[Path, str]:
    """Return the PTT crawl output to analyze."""
    if preferred and preferred.exists():
        return preferred, preferred.name

    if FORUM_REAL_PATH.exists():
        return FORUM_REAL_PATH, "ptt_crawl"

    raise FileNotFoundError(
        "PTT forum signals not found. Run `make ptt` first to create "
        f"{FORUM_REAL_PATH}."
    )


def summarize_forum_signals(signals: list[dict]) -> dict:
    if not signals:
        return {
            "threads_analyzed": 0,
            "pricing_question_ratio": 0.0,
            "tool_seeking_ratio": 0.0,
            "top_keywords": [],
            "top_districts": [],
            "boards": [],
            "median_extracted_rent_ntd": None,
            "example_titles": [],
        }

    keywords = Counter()
    districts = Counter()
    boards = Counter()
    extracted_prices: list[int] = []
    tool_posts = 0

    for item in signals:
        keywords.update(item.get("keywords", []))
        boards.update([item.get("board")] if item.get("board") else [])
        for district in item.get("districts", []):
            districts[district] = districts.get(district, 0) + 1
        extracted_prices.extend(item.get("extracted_prices_ntd", []))
        if "tool" in item.get("keywords", []):
            tool_posts += 1

    example_titles = [
        {
            "board": item.get("board"),
            "title": item.get("title"),
            "contains_pricing_question": item.get("contains_pricing_question"),
            "districts": item.get("districts", []),
        }
        for item in signals[:5]
    ]

    median_rent = None
    if extracted_prices:
        median_rent = float(pd.Series(extracted_prices).median())

    return {
        "threads_analyzed": len(signals),
        "pricing_question_ratio": round(
            sum(1 for item in signals if item.get("contains_pricing_question"))
            / len(signals),
            3,
        ),
        "tool_seeking_ratio": round(tool_posts / len(signals), 3),
        "top_keywords": keywords.most_common(8),
        "top_districts": districts.most_common(8),
        "boards": boards.most_common(),
        "median_extracted_rent_ntd": median_rent,
        "example_titles": example_titles,
    }
