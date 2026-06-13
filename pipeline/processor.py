"""Batch processing pipeline for rental market analytics."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from pipeline.db import DistrictMetric, PricingRecommendation, RentalTransaction, init_db
from pipeline.kmeans_segmentation import run_kmeans_segmentation


def load_transactions_df(session: Session) -> pd.DataFrame:
    rows = session.query(RentalTransaction).all()
    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(
        [
            {
                "district": row.district,
                "building_type": row.building_type,
                "area_ping": row.area_ping,
                "rent_ntd": row.rent_ntd,
                "rent_per_ping": row.rent_per_ping,
                "transaction_date": row.transaction_date,
            }
            for row in rows
        ]
    )


def compute_district_metrics(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    grouped = (
        df.groupby(["district", "building_type"])
        .agg(
            sample_size=("rent_per_ping", "count"),
            median_rent_per_ping=("rent_per_ping", "median"),
            p25_rent_per_ping=("rent_per_ping", lambda s: np.percentile(s, 25)),
            p75_rent_per_ping=("rent_per_ping", lambda s: np.percentile(s, 75)),
            median_rent_ntd=("rent_ntd", "median"),
        )
        .reset_index()
    )
    grouped["updated_at"] = datetime.utcnow()
    return grouped


def build_recommendations(metrics_df: pd.DataFrame, area_ping: float = 10.0) -> pd.DataFrame:
    if metrics_df.empty:
        return pd.DataFrame()

    recs = metrics_df.copy()
    recs["recommended_rent_low"] = (
        recs["p25_rent_per_ping"] * area_ping
    ).round().astype(int)
    recs["recommended_rent_mid"] = (
        recs["median_rent_per_ping"] * area_ping
    ).round().astype(int)
    recs["recommended_rent_high"] = (
        recs["p75_rent_per_ping"] * area_ping
    ).round().astype(int)
    recs["area_ping"] = area_ping
    recs["confidence_score"] = np.clip(recs["sample_size"] / 20.0, 0.35, 0.95)
    recs["updated_at"] = datetime.utcnow()
    return recs[
        [
            "district",
            "building_type",
            "area_ping",
            "recommended_rent_low",
            "recommended_rent_mid",
            "recommended_rent_high",
            "confidence_score",
            "updated_at",
        ]
    ]


def persist_metrics(session: Session, metrics_df: pd.DataFrame) -> int:
    session.query(DistrictMetric).delete()
    count = 0
    for _, row in metrics_df.iterrows():
        session.add(
            DistrictMetric(
                district=row["district"],
                building_type=row["building_type"],
                sample_size=int(row["sample_size"]),
                median_rent_per_ping=float(row["median_rent_per_ping"]),
                p25_rent_per_ping=float(row["p25_rent_per_ping"]),
                p75_rent_per_ping=float(row["p75_rent_per_ping"]),
                median_rent_ntd=float(row["median_rent_ntd"]),
                updated_at=row["updated_at"],
            )
        )
        count += 1
    return count


def persist_recommendations(session: Session, recs_df: pd.DataFrame) -> int:
    session.query(PricingRecommendation).delete()
    count = 0
    for _, row in recs_df.iterrows():
        session.add(
            PricingRecommendation(
                district=row["district"],
                building_type=row["building_type"],
                area_ping=float(row["area_ping"]),
                recommended_rent_low=int(row["recommended_rent_low"]),
                recommended_rent_mid=int(row["recommended_rent_mid"]),
                recommended_rent_high=int(row["recommended_rent_high"]),
                confidence_score=float(row["confidence_score"]),
                updated_at=row["updated_at"],
            )
        )
        count += 1
    return count


def run_pipeline(session: Session, default_area_ping: float = 10.0) -> dict:
    df = load_transactions_df(session)
    metrics_df = compute_district_metrics(df)
    recs_df = build_recommendations(metrics_df, area_ping=default_area_ping)

    metric_count = persist_metrics(session, metrics_df)
    rec_count = persist_recommendations(session, recs_df)
    cluster_summary = run_kmeans_segmentation(session)

    return {
        "transactions": len(df),
        "district_metrics": metric_count,
        "recommendations": rec_count,
        "kmeans_clusters": cluster_summary.get("clusters", 0),
        "updated_at": datetime.utcnow().isoformat(),
    }


def main() -> None:
    init_db()
    from pipeline.db import session_scope

    with session_scope() as session:
        summary = run_pipeline(session)
    print("Pipeline completed:", summary)


if __name__ == "__main__":
    main()
