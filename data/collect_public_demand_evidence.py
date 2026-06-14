"""Build a public-data-only demand-evidence report for LeasePulse Taipei.

Use this when you do not conduct private interviews. It combines reproducible public
sources only:
  1. PTT rental-board discussions from the past two years
  2. Google Trends search-interest signals from the past 24 months
  3. Current App Store reviews from housing/rental apps
  4. Current competitor / analogous pricing pages

Output:
  data/processed/demand_evidence_public_report.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def rel_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def summarize_forum(path: Path) -> dict:
    rows = load_json(path, [])
    keyword_counts = Counter(k for row in rows for k in row.get("keywords", []))
    district_counts = Counter(d for row in rows for d in row.get("districts", []))
    prices = [p for row in rows for p in row.get("extracted_prices_ntd", []) if 2000 <= p <= 300000]
    pricing_questions = sum(1 for row in rows if row.get("contains_pricing_question"))
    return {
        "source_file": rel_path(path),
        "threads_analyzed": len(rows),
        "pricing_question_ratio": round(pricing_questions / len(rows), 3) if rows else None,
        "top_keywords": keyword_counts.most_common(10),
        "top_districts": district_counts.most_common(10),
        "median_extracted_rent_ntd": int(statistics.median(prices)) if prices else None,
        "rent_mentions_observed": len(prices),
    }


def summarize_trends(path: Path) -> dict:
    payload = load_json(path, {})
    if not payload:
        return {"source_file": rel_path(path), "available": False}
    return {
        "source_file": rel_path(path),
        "available": payload.get("available", bool(payload.get("keyword_stats"))),
        "source": payload.get("source"),
        "timeframe": payload.get("timeframe"),
        "geo": payload.get("geo"),
        "top_keyword_by_mean_interest": payload.get("top_keyword_by_mean_interest"),
        "keyword_stats": payload.get("keyword_stats", [])[:10],
        "note": payload.get("note"),
    }


def summarize_app_reviews(path: Path) -> dict:
    payload = load_json(path, {})
    if not payload:
        return {"source_file": rel_path(path), "available": False}
    summary = payload.get("summary", {})
    return {
        "source_file": rel_path(path),
        "available": True,
        "source": summary.get("source"),
        "since_date": summary.get("since_date"),
        "reviews_collected": summary.get("reviews_collected"),
        "average_rating": summary.get("average_rating"),
        "top_pain_keywords": summary.get("top_pain_keywords", [])[:10],
    }


def summarize_competitors(path: Path) -> dict:
    payload = load_json(path, {})
    if not payload:
        return {"source_file": rel_path(path), "available": False}
    rows = payload.get("records", [])

    def is_own_product(row: dict) -> bool:
        return "leasepulse" in (row.get("product") or "").lower()

    incumbent_rows = [row for row in rows if not is_own_product(row)]
    summary = payload.get("summary", {})
    candidate_prices = [
        p for row in incumbent_rows for p in row.get("extracted_price_values_ntd", [])
    ]
    manual_prices = [
        row["manual_verified_price_ntd"]
        for row in incumbent_rows
        if row.get("manual_verified_price_ntd") is not None
    ]
    monthly_like = [p for p in candidate_prices if 50 <= p <= 5000]
    all_benchmarks = manual_prices or monthly_like
    return {
        "source_file": rel_path(path),
        "available": bool(rows),
        "source": summary.get("source"),
        "pages_checked": len(incumbent_rows),
        "products": [row["product"] for row in incumbent_rows],
        "manual_verified_benchmarks": [
            {
                "product": row["product"],
                "pricing_plan_name": row.get("pricing_plan_name"),
                "manual_verified_price_ntd": row["manual_verified_price_ntd"],
                "source_url": row["source_url"],
            }
            for row in incumbent_rows
            if row.get("manual_verified_price_ntd") is not None
        ],
        "candidate_price_values_ntd": sorted(set(candidate_prices))[:50],
        "median_monthly_like_price_ntd": int(statistics.median(all_benchmarks)) if all_benchmarks else None,
        "note": summary.get("note"),
    }


def build_report(args: argparse.Namespace) -> dict:
    forum = summarize_forum(ROOT / args.forum)
    trends = summarize_trends(ROOT / args.trends)
    app_reviews = summarize_app_reviews(ROOT / args.app_reviews)
    competitors = summarize_competitors(ROOT / args.competitors)

    evidence_sources = [
        "Taipei City real-price rental open data for market transactions",
        "Public PTT rental-board discussions limited to the past two years",
        "Google Trends search-interest data for the past 24 months",
        "Current App Store reviews from rental / housing apps",
        "Current public competitor and analogous pricing pages",
    ]

    report = {
        "generated_at": utc_now_iso(),
        "private_interviews_used": False,
        "methodology": {
            "statement": (
                "This MVP does not claim private interviews. Demand validation uses reproducible public evidence: "
                "PTT forum discussions, search trends, App Store reviews, competitor pricing pages, and Taipei open rental data."
            ),
            "evidence_sources": evidence_sources,
            "privacy_and_ethics": (
                "Forum and review content are public pages. The crawlers throttle requests, store source URLs, "
                "filter to recent/current data, and redact common phone/email/LINE identifiers. The outputs should be used "
                "as aggregate demand signals, not as private interview records."
            ),
        },
        "forum_summary": forum,
        "search_trends_summary": trends,
        "app_review_summary": app_reviews,
        "competitor_pricing_summary": competitors,
        "demand_conclusion": {
            "target_wedge": "Independent landlords managing 2-15 units in Greater Taipei",
            "evidence_strength": "Moderate; reproducible public evidence without private interviews",
            "why_need_exists": [
                "Forum posts reveal repeated rent-pricing, comparables, and vacancy discussions.",
                "Search-interest data shows whether rent-pricing keywords attract sustained attention.",
                "App reviews expose pain points in existing rental-search and landlord tools.",
                "Competitor/listing pricing pages show landlords already pay for visibility or rental-management workflows.",
            ],
            "recommended_positioning": "Free district snapshot; paid custom rent quote, alerts, and API access.",
        },
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build public-data-only demand evidence report")
    parser.add_argument("--forum", default="data/processed/forum_signals_real.json")
    parser.add_argument("--trends", default="data/processed/search_trends_real.json")
    parser.add_argument("--app-reviews", default="data/processed/app_reviews_real.json")
    parser.add_argument("--competitors", default="data/processed/competitor_pricing_real.json")
    parser.add_argument("--output", default="data/processed/demand_evidence_public_report.json")
    args = parser.parse_args()

    report = build_report(args)
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] public demand evidence report -> {output_path}")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
