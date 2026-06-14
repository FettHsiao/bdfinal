"""LeasePulse Taipei REST API."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from pipeline.db import (
    DistrictMetric,
    PricingRecommendation,
    RentalCluster,
    RentalTransaction,
    SessionLocal,
    init_db,
)

app = FastAPI(
    title="LeasePulse Taipei API",
    description="Rental pricing intelligence for Greater Taipei landlords",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HOME_LINKS = [
    ("/health", "Health check", "Verify the API is running"),
    ("/metrics/districts", "District metrics", "Rent statistics by district and building type"),
    (
        "/quote?district=大安區&building_type=住宅大樓(11層含以上有電梯)&area_ping=10",
        "Rent quote (example)",
        "Sample pricing band for a 10-ping unit in Da'an",
    ),
    ("/clusters", "Market clusters", "HW2 MapReduce K-Means segments"),
    ("/recommendations", "Recommendations", "Precomputed pricing bands"),
    ("/transactions/summary", "Transaction summary", "Dataset coverage overview"),
    ("/docs", "Swagger docs", "Interactive API explorer"),
]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> str:
    links_html = "\n".join(
        f"""
        <li>
          <a href="{path}"><strong>{title}</strong></a>
          <span>{desc}</span>
        </li>
        """
        for path, title, desc in HOME_LINKS
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>LeasePulse Taipei API</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      max-width: 760px;
      margin: 48px auto;
      padding: 0 20px;
      color: #1f2937;
      line-height: 1.5;
    }}
    h1 {{ color: #1f4e79; margin-bottom: 0.2rem; }}
    p.sub {{ color: #4b5563; margin-top: 0; }}
    ul {{ list-style: none; padding: 0; }}
    li {{
      border: 1px solid #dbeafe;
      background: #eef4fb;
      border-radius: 10px;
      padding: 14px 16px;
      margin: 10px 0;
    }}
    a {{ color: #1f4e79; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    li span {{ display: block; color: #6b7280; font-size: 0.92rem; margin-top: 4px; }}
    .hint {{ margin-top: 28px; font-size: 0.95rem; color: #374151; }}
  </style>
</head>
<body>
  <h1>LeasePulse Taipei API</h1>
  <p class="sub">Choose an endpoint to inspect live rental pricing data.</p>
  <ul>
    {links_html}
  </ul>
  <p class="hint">
    For the customer-facing product UI, run <code>make dashboard</code>
    locally or deploy the Streamlit app separately.
  </p>
</body>
</html>"""


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "leasepulse-api"}


@app.get("/metrics/districts")
def list_district_metrics(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(DistrictMetric).order_by(DistrictMetric.district).all()
    return [
        {
            "district": row.district,
            "building_type": row.building_type,
            "sample_size": row.sample_size,
            "median_rent_per_ping": row.median_rent_per_ping,
            "p25_rent_per_ping": row.p25_rent_per_ping,
            "p75_rent_per_ping": row.p75_rent_per_ping,
            "median_rent_ntd": row.median_rent_ntd,
            "updated_at": row.updated_at.isoformat(),
        }
        for row in rows
    ]


@app.get("/recommendations")
def list_recommendations(
    district: Optional[str] = Query(default=None),
    building_type: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    query = db.query(PricingRecommendation)
    if district:
        query = query.filter(PricingRecommendation.district == district)
    if building_type:
        query = query.filter(PricingRecommendation.building_type == building_type)

    rows = query.order_by(
        PricingRecommendation.district, PricingRecommendation.building_type
    ).all()
    return [
        {
            "district": row.district,
            "building_type": row.building_type,
            "area_ping": row.area_ping,
            "recommended_rent_low": row.recommended_rent_low,
            "recommended_rent_mid": row.recommended_rent_mid,
            "recommended_rent_high": row.recommended_rent_high,
            "confidence_score": row.confidence_score,
            "updated_at": row.updated_at.isoformat(),
        }
        for row in rows
    ]


@app.get("/quote")
def quote_rent(
    district: str = Query(..., description="District name, e.g. Da'an"),
    building_type: str = Query(..., description="elevator_apartment, walkup, studio"),
    area_ping: float = Query(..., gt=0, description="Unit area in ping"),
    db: Session = Depends(get_db),
) -> dict:
    metric = (
        db.query(DistrictMetric)
        .filter(
            DistrictMetric.district == district,
            DistrictMetric.building_type == building_type,
        )
        .first()
    )
    if not metric:
        raise HTTPException(
            status_code=404,
            detail=f"No metrics found for {district} / {building_type}",
        )

    low = int(round(metric.p25_rent_per_ping * area_ping))
    mid = int(round(metric.median_rent_per_ping * area_ping))
    high = int(round(metric.p75_rent_per_ping * area_ping))
    confidence = min(0.95, max(0.35, metric.sample_size / 20.0))

    return {
        "district": district,
        "building_type": building_type,
        "area_ping": area_ping,
        "recommended_rent_low": low,
        "recommended_rent_mid": mid,
        "recommended_rent_high": high,
        "rent_per_ping_low": round(metric.p25_rent_per_ping, 2),
        "rent_per_ping_mid": round(metric.median_rent_per_ping, 2),
        "rent_per_ping_high": round(metric.p75_rent_per_ping, 2),
        "district_median_rent_ntd": round(metric.median_rent_ntd, 0),
        "confidence_score": confidence,
        "sample_size": metric.sample_size,
        "currency": "TWD",
        "data_source": "taipei_open_data_real_price_weekly",
        "updated_at": metric.updated_at.isoformat(),
        "pricing_guidance": {
            "conservative": {
                "label": "Conservative (P25)",
                "monthly_rent_ntd": low,
                "rent_per_ping_ntd": round(metric.p25_rent_per_ping, 2),
                "note": "Lower vacancy risk; suitable when you need a tenant quickly.",
            },
            "market": {
                "label": "Market median",
                "monthly_rent_ntd": mid,
                "rent_per_ping_ntd": round(metric.median_rent_per_ping, 2),
                "note": "Balanced target based on recent comparable transactions.",
            },
            "aggressive": {
                "label": "Aggressive (P75)",
                "monthly_rent_ntd": high,
                "rent_per_ping_ntd": round(metric.p75_rent_per_ping, 2),
                "note": "Higher upside, but may lengthen vacancy if the unit is average.",
            },
        },
        "annual_rent_estimate": {
            "low_ntd": low * 12,
            "mid_ntd": mid * 12,
            "high_ntd": high * 12,
        },
    }


@app.get("/clusters")
def list_clusters(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(RentalCluster).order_by(RentalCluster.cluster_id).all()
    return [
        {
            "cluster_id": row.cluster_id,
            "segment_label": row.segment_label,
            "centroid_area_ping": row.centroid_area_ping,
            "centroid_rent_per_ping": row.centroid_rent_per_ping,
            "sample_size": row.sample_size,
            "updated_at": row.updated_at.isoformat(),
        }
        for row in rows
    ]


@app.get("/transactions/summary")
def transaction_summary(db: Session = Depends(get_db)) -> dict:
    rows = db.query(RentalTransaction).all()
    districts = sorted({row.district for row in rows})
    return {
        "total_transactions": len(rows),
        "districts": districts,
        "latest_ingested_at": max((row.ingested_at for row in rows), default=None),
    }


@app.post("/admin/reprocess")
def reprocess(db: Session = Depends(get_db)) -> dict:
    if os.getenv("ALLOW_REPROCESS", "true").lower() != "true":
        raise HTTPException(status_code=403, detail="Reprocess disabled")
    from pipeline.processor import run_pipeline

    return run_pipeline(db)
