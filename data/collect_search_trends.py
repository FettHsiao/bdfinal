"""Collect two-year Google Trends demand signals for rent-pricing keywords.

This script creates reproducible public demand evidence without private interviews.
It calls the public Google Trends widget API directly (more reliable than pytrends on
recent urllib3 versions).

Outputs:
  data/processed/search_trends_real.csv
  data/processed/search_trends_real.json

Example:
  python -m data.collect_search_trends \
    --keywords 台北租金 租屋行情 租金行情 實價登錄租賃 租屋價格 \
    --timeframe "today 24-m" \
    --geo TW
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import requests

DEFAULT_KEYWORDS = [
    "台北租金",
    "租屋行情",
    "租金行情",
    "實價登錄租賃",
    "租屋價格",
]

TRENDS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_trends_json(text: str) -> dict:
    if text.startswith(")]}'"):
        text = text[5:]
    return json.loads(text)


def resolve_timeframe(timeframe: str) -> str:
    if not timeframe.startswith("today"):
        return timeframe

    end = datetime.now().date()
    if "24-m" in timeframe:
        start = end - timedelta(days=730)
    elif "5-y" in timeframe:
        start = end - timedelta(days=365 * 5)
    elif "12-m" in timeframe:
        start = end - timedelta(days=365)
    else:
        start = end - timedelta(days=730)
    return f"{start} {end}"


def make_trends_session(geo: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(TRENDS_HEADERS)
    session.get(f"https://trends.google.com/trends/?geo={geo}", timeout=20)
    return session


def fetch_keyword_series(
    session: requests.Session,
    keyword: str,
    timeframe: str,
    geo: str,
) -> list[dict]:
    resolved_timeframe = resolve_timeframe(timeframe)
    payload = {
        "comparisonItem": [{"keyword": keyword, "geo": geo, "time": resolved_timeframe}],
        "category": 0,
        "property": "",
    }
    explore_params = {
        "hl": "zh-TW",
        "tz": "-480",
        "req": json.dumps(payload, separators=(",", ":")),
    }
    explore_resp = session.get(
        "https://trends.google.com/trends/api/explore",
        params=explore_params,
        timeout=20,
    )
    explore_resp.raise_for_status()
    explore_data = parse_trends_json(explore_resp.text)
    widget = next(item for item in explore_data["widgets"] if item.get("id") == "TIMESERIES")

    multiline_params = {
        "hl": "zh-TW",
        "tz": "-480",
        "req": json.dumps(widget["request"], separators=(",", ":")),
        "token": widget["token"],
    }
    multiline_resp = session.get(
        "https://trends.google.com/trends/api/widgetdata/multiline/json",
        params=multiline_params,
        timeout=20,
    )
    multiline_resp.raise_for_status()
    multiline_data = parse_trends_json(multiline_resp.text)
    timeline = multiline_data.get("default", {}).get("timelineData", [])

    rows: list[dict] = []
    for point in timeline:
        if not point.get("hasData") or not point.get("value"):
            continue
        week = datetime.fromtimestamp(int(point["time"]), tz=timezone.utc).date().isoformat()
        rows.append(
            {
                "week": week,
                "keyword": keyword,
                "interest": int(point["value"][0]),
            }
        )
    return rows


def collect_trends(keywords: list[str], timeframe: str, geo: str) -> tuple[pd.DataFrame, str | None]:
    session = make_trends_session(geo)
    frames: list[pd.DataFrame] = []
    errors: list[str] = []

    for keyword in keywords:
        try:
            rows = fetch_keyword_series(session, keyword, timeframe=timeframe, geo=geo)
            if not rows:
                errors.append(f"{keyword}: empty timeline")
                continue
            frames.append(pd.DataFrame(rows))
            time.sleep(1.5)
        except Exception as exc:
            errors.append(f"{keyword}: {exc}")
            time.sleep(2.0)

    error_note = None
    if errors and not frames:
        error_note = f"Google Trends request failed: {'; '.join(errors)}"
    elif errors:
        error_note = f"Partial Google Trends failures: {'; '.join(errors)}"

    if not frames:
        return pd.DataFrame(columns=["week", "keyword", "interest"]), error_note

    result = pd.concat(frames, ignore_index=True)
    result["source"] = "Google Trends public widget API"
    result["timeframe"] = resolve_timeframe(timeframe)
    result["geo"] = geo
    result["collected_at"] = utc_now_iso()
    return result, error_note


def summarize_trends(
    df: pd.DataFrame,
    keywords: list[str],
    timeframe: str,
    geo: str,
    error_note: str | None = None,
) -> dict:
    resolved_timeframe = resolve_timeframe(timeframe)
    if df.empty:
        stats = []
        top_keyword = None
    else:
        summary = (
            df.groupby("keyword")
            .agg(
                mean_interest=("interest", "mean"),
                max_interest=("interest", "max"),
                latest_interest=("interest", lambda x: float(x.iloc[-1])),
                weeks_observed=("interest", "count"),
            )
            .reset_index()
            .sort_values("mean_interest", ascending=False)
        )
        summary[["mean_interest", "max_interest", "latest_interest"]] = summary[
            ["mean_interest", "max_interest", "latest_interest"]
        ].round(2)
        stats = summary.to_dict(orient="records")
        top_keyword = stats[0]["keyword"] if stats else None

    return {
        "generated_at": utc_now_iso(),
        "source": "Google Trends",
        "method": "Google Trends public widget API (interest_over_time)",
        "timeframe": resolved_timeframe,
        "geo": geo,
        "keywords": keywords,
        "top_keyword_by_mean_interest": top_keyword,
        "keyword_stats": stats,
        "note": error_note
        or "Google Trends values are relative search interest scores from 0 to 100, not absolute search volume.",
        "available": df.empty is False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect two-year Google Trends rent-pricing demand evidence")
    parser.add_argument("--keywords", nargs="+", default=DEFAULT_KEYWORDS)
    parser.add_argument("--timeframe", default="today 24-m", help="Default uses the most recent two years")
    parser.add_argument("--geo", default="TW")
    parser.add_argument("--csv-output", default="data/processed/search_trends_real.csv")
    parser.add_argument("--json-output", default="data/processed/search_trends_real.json")
    args = parser.parse_args()

    df, error_note = collect_trends(args.keywords, timeframe=args.timeframe, geo=args.geo)
    if error_note:
        print(f"[WARN] {error_note}")
    summary = summarize_trends(df, args.keywords, timeframe=args.timeframe, geo=args.geo, error_note=error_note)

    csv_path = ROOT / args.csv_output
    json_path = ROOT / args.json_output
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[DONE] Google Trends weekly data: {len(df)} rows -> {csv_path}")
    print(f"[DONE] Google Trends summary -> {json_path}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
