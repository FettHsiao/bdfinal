"""Collect recent App Store reviews for rental / housing apps.

This is a public-data alternative to private interviews. It captures recent user pain points
from app reviews and filters them to the past two years by default.

Outputs:
  data/processed/app_reviews_real.json
  data/processed/app_reviews_real.csv

Example:
  python scripts/collect_app_store_reviews.py --since-years 2
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests

DEFAULT_APPS = [
    {"app_name": "591房屋交易", "app_id": "448156496", "country": "tw"},
    # Add more official App Store app IDs here if you want broader coverage.
]

PAIN_KEYWORDS = {
    "pricing": r"價格|租金|房租|太貴|行情|實價|價錢",
    "trust": r"假|詐騙|不實|騙|仲介|廣告|真實",
    "search_quality": r"搜尋|篩選|地圖|定位|找不到|排序",
    "data_quality": r"更新|過期|重複|資訊|資料|照片",
    "ads": r"廣告|付費|收費|會員|置頂",
    "contact": r"聯絡|電話|訊息|客服|回覆",
}


@dataclass
class AppReviewSignal:
    app_name: str
    app_id: str
    country: str
    review_id: str
    title: str
    rating: int | None
    updated: str | None
    content_redacted: str
    pain_keywords: list[str]
    source_url: str
    collected_at: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def compute_since_date(since_date: str | None, since_years: int) -> date:
    if since_date:
        return datetime.strptime(since_date, "%Y-%m-%d").date()
    return date.today() - timedelta(days=365 * since_years)


def parse_review_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def redact_pii(text: str) -> str:
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL_REDACTED]", text)
    text = re.sub(r"(?<!\d)09\d{2}[-\s]?\d{3}[-\s]?\d{3}(?!\d)", "[PHONE_REDACTED]", text)
    return text


def extract_pain_keywords(text: str) -> list[str]:
    return sorted(k for k, pattern in PAIN_KEYWORDS.items() if re.search(pattern, text, re.I))


def fetch_reviews(app: dict, page: int, timeout: int = 30) -> dict:
    country = app.get("country", "tw")
    app_id = app["app_id"]
    url = f"https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
    response = requests.get(url, timeout=timeout, headers={"User-Agent": "LeasePulseTaipeiAcademicCrawler/1.0"})
    response.raise_for_status()
    return response.json()


def iter_reviews(app: dict, max_pages: int, sleep_seconds: float) -> Iterable[AppReviewSignal]:
    for page in range(1, max_pages + 1):
        data = fetch_reviews(app, page=page)
        feed = data.get("feed", {})
        entries = feed.get("entry", [])
        if isinstance(entries, dict):
            entries = [entries]
        # Page 1 can include the app metadata as the first entry; review entries have im:rating.
        review_count = 0
        for entry in entries:
            rating_field = entry.get("im:rating")
            if rating_field is None:
                continue
            review_count += 1
            title = entry.get("title", {}).get("label", "")
            content = entry.get("content", {}).get("label", "")
            updated = entry.get("updated", {}).get("label")
            review_id = entry.get("id", {}).get("label", "")
            source_url = entry.get("link", {}).get("attributes", {}).get("href", "")
            rating = None
            try:
                rating = int(rating_field.get("label"))
            except Exception:
                pass
            combined = f"{title}\n{content}"
            yield AppReviewSignal(
                app_name=app["app_name"],
                app_id=app["app_id"],
                country=app.get("country", "tw"),
                review_id=review_id,
                title=title,
                rating=rating,
                updated=updated,
                content_redacted=redact_pii(content),
                pain_keywords=extract_pain_keywords(combined),
                source_url=source_url,
                collected_at=utc_now_iso(),
            )
        if review_count == 0:
            break
        time.sleep(sleep_seconds)


def summarize(rows: list[dict], since: date) -> dict:
    ratings = [r["rating"] for r in rows if r.get("rating") is not None]
    pain_counter = Counter(k for r in rows for k in r.get("pain_keywords", []))
    app_counter = Counter(r["app_name"] for r in rows)
    return {
        "generated_at": utc_now_iso(),
        "source": "Apple App Store public RSS customer reviews",
        "since_date": since.isoformat(),
        "reviews_collected": len(rows),
        "apps_reviewed": dict(app_counter),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "top_pain_keywords": pain_counter.most_common(10),
        "note": "Reviews are public user-generated content and are treated as qualitative demand/pain-point evidence, not as interviews.",
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            flat = {k: json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v for k, v in row.items()}
            writer.writerow(flat)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect recent App Store review demand evidence")
    parser.add_argument("--apps-json", default=None, help="Optional JSON list of {'app_name','app_id','country'} records")
    parser.add_argument("--since-date", default=None)
    parser.add_argument("--since-years", type=int, default=2)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=0.8)
    parser.add_argument("--json-output", default="data/processed/app_reviews_real.json")
    parser.add_argument("--csv-output", default="data/processed/app_reviews_real.csv")
    args = parser.parse_args()

    apps = DEFAULT_APPS
    if args.apps_json:
        apps = json.loads((ROOT / args.apps_json).read_text(encoding="utf-8"))

    since = compute_since_date(args.since_date, args.since_years)
    signals: list[AppReviewSignal] = []
    for app in apps:
        print(f"[INFO] fetching App Store reviews: {app['app_name']} ({app['app_id']})")
        for signal in iter_reviews(app, max_pages=args.max_pages, sleep_seconds=args.sleep):
            updated_date = parse_review_date(signal.updated)
            if updated_date is None or updated_date < since:
                continue
            signals.append(signal)

    rows = [asdict(s) for s in signals]
    summary = summarize(rows, since=since)
    result = {"summary": summary, "reviews": rows}

    json_path = ROOT / args.json_output
    csv_path = ROOT / args.csv_output
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, rows)

    print(f"[DONE] App Store reviews: {len(rows)} -> {json_path}")
    print(f"[DONE] App Store review CSV -> {csv_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
