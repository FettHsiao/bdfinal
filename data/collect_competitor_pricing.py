"""Collect current competitor pricing / analogous-product benchmarks from public pages.

This script does not claim interview evidence. It records current public pricing pages,
checked time, extracted price-like values, manually verified prices, and source URLs for
report reproducibility.

Outputs:
  data/processed/competitor_pricing_real.json
  data/processed/competitor_pricing_real.csv

Example:
  python -m data.collect_competitor_pricing --sources data/sources/competitor_pricing_sources.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests
from bs4 import BeautifulSoup

DEFAULT_SOURCE_FILE = "data/sources/competitor_pricing_sources.json"

PRICE_RE = re.compile(
    r"(?:NT\$|NTD|台幣|新台幣|\$|＄)?\s*(?P<num>\d{1,3}(?:,\d{3})+|\d{2,6})(?:\s*(?:元|塊|/月|／月|每月|月|戶|筆))?"
)
PERCENT_RE = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*%")


@dataclass
class CompetitorPricingRecord:
    product: str
    category: str
    source_url: str
    checked_at: str
    pricing_plan_name: str | None
    manual_verified_price_ntd: int | None
    page_title: str | None
    extracted_price_values_ntd: list[int]
    extracted_percent_values: list[float]
    pricing_text_snippet: str
    notes: str | None
    crawl_status: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def allowed_by_robots(url: str, user_agent: str = "LeasePulseTaipeiAcademicCrawler/1.0") -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception as exc:
        print(f"[WARN] robots.txt unavailable for {parsed.netloc} ({exc}); continuing with throttled access")
        return True


def fetch_page(url: str, timeout: int = 30) -> str:
    headers = {"User-Agent": "LeasePulseTaipeiAcademicCrawler/1.0"}
    try:
        response = requests.get(url, timeout=timeout, headers=headers, verify=True)
    except requests.exceptions.SSLError:
        response = requests.get(url, timeout=timeout, headers=headers, verify=False)
    response.raise_for_status()
    if response.encoding is None:
        response.encoding = response.apparent_encoding
    return response.text


def clean_text(html: str) -> tuple[str | None, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return title, text


def extract_prices(text: str) -> list[int]:
    values = []
    for m in PRICE_RE.finditer(text):
        raw = m.group("num").replace(",", "")
        try:
            value = int(raw)
        except ValueError:
            continue
        if 50 <= value <= 300000:
            values.append(value)
    return sorted(set(values))[:30]


def extract_percents(text: str) -> list[float]:
    values = []
    for m in PERCENT_RE.finditer(text):
        try:
            value = float(m.group("num"))
        except ValueError:
            continue
        if 0 < value <= 100:
            values.append(value)
    return sorted(set(values))[:20]


def best_pricing_snippet(text: str, max_len: int = 700) -> str:
    anchors = ["價格", "費用", "方案", "月", "元", "收費", "租金", "抽成", "刊登"]
    positions = [text.find(a) for a in anchors if text.find(a) >= 0]
    if positions:
        start = max(0, min(positions) - 120)
        return text[start : start + max_len]
    return text[:max_len]


def merge_prices(extracted: list[int], manual: int | None) -> list[int]:
    values = list(extracted)
    if manual is not None:
        values.append(manual)
    return sorted(set(values))


def collect(records: list[dict], sleep_seconds: float, skip_robots_check: bool) -> list[CompetitorPricingRecord]:
    output: list[CompetitorPricingRecord] = []
    for item in records:
        if item.get("enabled") is False:
            continue

        url = item["source_url"]
        product = item.get("product") or urlparse(url).netloc
        manual_price = item.get("manual_verified_price_ntd")
        plan_name = item.get("pricing_plan_name")
        checked_at = utc_now_iso()

        print(f"[INFO] fetching competitor pricing: {product} -> {url}")
        page_title: str | None = None
        extracted_prices: list[int] = []
        extracted_percents: list[float] = []
        snippet = ""
        crawl_status = "manual_only"
        notes = item.get("notes")

        try:
            if not skip_robots_check and not allowed_by_robots(url):
                crawl_status = "robots_blocked"
                notes = (notes or "") + " robots.txt blocked automated fetch; manual price retained."
            else:
                html = fetch_page(url)
                page_title, text = clean_text(html)
                extracted_prices = extract_prices(text)
                extracted_percents = extract_percents(text)
                snippet = best_pricing_snippet(text)
                crawl_status = "crawled"
        except Exception as exc:
            crawl_status = "fetch_failed"
            notes = (notes or "") + f" Crawl failed: {exc}"
            print(f"[WARN] crawl failed for {url}: {exc}")

        if manual_price is not None and crawl_status != "crawled":
            snippet = snippet or (
                f"Manual verified benchmark: {plan_name or product} = NT${manual_price:,} "
                f"(checked {item.get('checked_date', 'N/A')})."
            )

        output.append(
            CompetitorPricingRecord(
                product=product,
                category=item.get("category", "competitor_or_analogous_product"),
                source_url=url,
                checked_at=checked_at,
                pricing_plan_name=plan_name,
                manual_verified_price_ntd=manual_price,
                page_title=page_title,
                extracted_price_values_ntd=merge_prices(extracted_prices, manual_price),
                extracted_percent_values=extracted_percents,
                pricing_text_snippet=snippet,
                notes=notes,
                crawl_status=crawl_status,
            )
        )
        time.sleep(sleep_seconds)
    return output


def summarize(rows: list[dict]) -> dict:
    prices = [p for row in rows for p in row.get("extracted_price_values_ntd", [])]
    manual_prices = [
        row["manual_verified_price_ntd"]
        for row in rows
        if row.get("manual_verified_price_ntd") is not None
    ]
    percents = [p for row in rows for p in row.get("extracted_percent_values", [])]
    verified_benchmarks = [
        {
            "product": row["product"],
            "pricing_plan_name": row.get("pricing_plan_name"),
            "manual_verified_price_ntd": row["manual_verified_price_ntd"],
            "source_url": row["source_url"],
        }
        for row in rows
        if row.get("manual_verified_price_ntd") is not None
    ]
    return {
        "generated_at": utc_now_iso(),
        "source": "Current public competitor / analogous pricing pages",
        "pages_checked": len(rows),
        "products": [row["product"] for row in rows],
        "manual_verified_benchmarks": verified_benchmarks,
        "price_values_observed_ntd": sorted(set(prices))[:50],
        "manual_verified_prices_ntd": sorted(set(manual_prices)),
        "percent_values_observed": sorted(set(percents))[:30],
        "note": (
            "Manual verified prices are checked against public pages. "
            "Extracted numbers are candidates and should be cited with source URLs."
        ),
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
    parser = argparse.ArgumentParser(description="Collect current competitor pricing benchmarks from public pages")
    parser.add_argument("--sources", default=DEFAULT_SOURCE_FILE)
    parser.add_argument("--json-output", default="data/processed/competitor_pricing_real.json")
    parser.add_argument("--csv-output", default="data/processed/competitor_pricing_real.csv")
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--skip-robots-check", action="store_true", help="Use only if you have already verified access is allowed")
    args = parser.parse_args()

    source_path = ROOT / args.sources
    source_records = json.loads(source_path.read_text(encoding="utf-8"))
    records = collect(source_records, sleep_seconds=args.sleep, skip_robots_check=args.skip_robots_check)
    rows = [asdict(record) for record in records]
    result = {"summary": summarize(rows), "records": rows}

    json_path = ROOT / args.json_output
    csv_path = ROOT / args.csv_output
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(csv_path, rows)

    print(f"[DONE] competitor pricing records: {len(rows)} -> {json_path}")
    print(f"[DONE] competitor pricing CSV -> {csv_path}")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
