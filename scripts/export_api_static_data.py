#!/usr/bin/env python3
"""Export SQLite demo payloads to JSON for Vercel (read-only serverless API)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pipeline.db import (
    DistrictMetric,
    PricingRecommendation,
    RentalCluster,
    RentalTransaction,
    SessionLocal,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "static_data"


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else value


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        metrics = db.query(DistrictMetric).order_by(DistrictMetric.district).all()
        recs = db.query(PricingRecommendation).order_by(
            PricingRecommendation.district, PricingRecommendation.building_type
        ).all()
        clusters = db.query(RentalCluster).order_by(RentalCluster.cluster_id).all()
        txns = db.query(RentalTransaction).all()

        (OUT / "district_metrics.json").write_text(
            json.dumps(
                [
                    {
                        "district": row.district,
                        "building_type": row.building_type,
                        "sample_size": row.sample_size,
                        "median_rent_per_ping": row.median_rent_per_ping,
                        "p25_rent_per_ping": row.p25_rent_per_ping,
                        "p75_rent_per_ping": row.p75_rent_per_ping,
                        "median_rent_ntd": row.median_rent_ntd,
                        "updated_at": iso(row.updated_at),
                    }
                    for row in metrics
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (OUT / "recommendations.json").write_text(
            json.dumps(
                [
                    {
                        "district": row.district,
                        "building_type": row.building_type,
                        "area_ping": row.area_ping,
                        "recommended_rent_low": row.recommended_rent_low,
                        "recommended_rent_mid": row.recommended_rent_mid,
                        "recommended_rent_high": row.recommended_rent_high,
                        "confidence_score": row.confidence_score,
                        "updated_at": iso(row.updated_at),
                    }
                    for row in recs
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (OUT / "clusters.json").write_text(
            json.dumps(
                [
                    {
                        "cluster_id": row.cluster_id,
                        "segment_label": row.segment_label,
                        "centroid_area_ping": row.centroid_area_ping,
                        "centroid_rent_per_ping": row.centroid_rent_per_ping,
                        "sample_size": row.sample_size,
                        "updated_at": iso(row.updated_at),
                    }
                    for row in clusters
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        districts = sorted({row.district for row in txns})
        latest = max((row.ingested_at for row in txns), default=None)
        (OUT / "transactions_summary.json").write_text(
            json.dumps(
                {
                    "total_transactions": len(txns),
                    "districts": districts,
                    "latest_ingested_at": iso(latest),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        db.close()

    print(f"Wrote API static payloads to {OUT}")


if __name__ == "__main__":
    main()
