"""LeasePulse Taipei REST API."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from pipeline.db import (
    DistrictMetric,
    PricingRecommendation,
    RentalCluster,
    RentalTransaction,
    SessionLocal,
    init_db,
)
from pipeline.processor import run_pipeline

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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def startup() -> None:
    init_db()


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
        "confidence_score": confidence,
        "sample_size": metric.sample_size,
        "currency": "TWD",
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
    return run_pipeline(db)
