"""Read-only API payloads for serverless deployments (no SQLite)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pipeline.db import is_serverless_runtime

STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "static_data"


def is_static_api_mode() -> bool:
    return is_serverless_runtime()


@lru_cache(maxsize=1)
def _load(name: str) -> Any:
    path = STATIC_DIR / name
    if not path.exists():
        return [] if name.endswith("s.json") else {}
    return json.loads(path.read_text(encoding="utf-8"))


def district_metrics() -> list[dict]:
    return list(_load("district_metrics.json"))


def recommendations(
    district: str | None = None,
    building_type: str | None = None,
) -> list[dict]:
    rows = list(_load("recommendations.json"))
    if district:
        rows = [row for row in rows if row["district"] == district]
    if building_type:
        rows = [row for row in rows if row["building_type"] == building_type]
    return rows


def clusters() -> list[dict]:
    return list(_load("clusters.json"))


def transactions_summary() -> dict:
    return dict(_load("transactions_summary.json"))


def quote(district: str, building_type: str, area_ping: float) -> dict | None:
    metric = next(
        (
            row
            for row in district_metrics()
            if row["district"] == district and row["building_type"] == building_type
        ),
        None,
    )
    if not metric:
        return None

    low = int(round(metric["p25_rent_per_ping"] * area_ping))
    mid = int(round(metric["median_rent_per_ping"] * area_ping))
    high = int(round(metric["p75_rent_per_ping"] * area_ping))
    confidence = min(0.95, max(0.35, metric["sample_size"] / 20.0))

    return {
        "district": district,
        "building_type": building_type,
        "area_ping": area_ping,
        "recommended_rent_low": low,
        "recommended_rent_mid": mid,
        "recommended_rent_high": high,
        "rent_per_ping_low": round(metric["p25_rent_per_ping"], 2),
        "rent_per_ping_mid": round(metric["median_rent_per_ping"], 2),
        "rent_per_ping_high": round(metric["p75_rent_per_ping"], 2),
        "district_median_rent_ntd": round(metric["median_rent_ntd"], 0),
        "confidence_score": confidence,
        "sample_size": metric["sample_size"],
        "currency": "TWD",
        "data_source": "taipei_open_data_real_price_weekly",
        "updated_at": metric["updated_at"],
        "pricing_guidance": {
            "conservative": {
                "label": "Conservative (P25)",
                "monthly_rent_ntd": low,
                "rent_per_ping_ntd": round(metric["p25_rent_per_ping"], 2),
                "note": "Lower vacancy risk; suitable when you need a tenant quickly.",
            },
            "market": {
                "label": "Market median",
                "monthly_rent_ntd": mid,
                "rent_per_ping_ntd": round(metric["median_rent_per_ping"], 2),
                "note": "Balanced target based on recent comparable transactions.",
            },
            "aggressive": {
                "label": "Aggressive (P75)",
                "monthly_rent_ntd": high,
                "rent_per_ping_ntd": round(metric["p75_rent_per_ping"], 2),
                "note": "Higher upside, but may lengthen vacancy if the unit is average.",
            },
        },
        "annual_rent_estimate": {
            "low_ntd": low * 12,
            "mid_ntd": mid * 12,
            "high_ntd": high * 12,
        },
    }
