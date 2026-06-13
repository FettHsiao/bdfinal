"""Segment rental transactions with HW2 MapReduce K-Means."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from pipeline.db import RentalCluster, RentalTransaction
from pipeline.mapreduce_kmeans import run_mapreduce_kmeans


SEGMENT_LABELS = ["budget", "value", "premium", "luxury"]


def _standardize_features(df: pd.DataFrame) -> tuple[np.ndarray, dict]:
    features = df[["area_ping", "rent_per_ping"]].astype(float)
    mean = features.mean()
    std = features.std().replace(0, 1.0)
    scaled = ((features - mean) / std).to_numpy()
    return scaled, {"mean": mean.to_dict(), "std": std.to_dict()}


def _label_clusters(centroids_raw: list[tuple[float, float]]) -> list[str]:
    ordered = sorted(
        enumerate(centroids_raw),
        key=lambda item: item[1][1],
    )
    labels = [""] * len(centroids_raw)
    for rank, (cluster_idx, _) in enumerate(ordered):
        labels[cluster_idx] = SEGMENT_LABELS[min(rank, len(SEGMENT_LABELS) - 1)]
    return labels


def run_kmeans_segmentation(
    session: Session,
    num_clusters: int = 4,
) -> dict:
    rows = session.query(RentalTransaction).all()
    if len(rows) < num_clusters:
        return {"clusters": 0, "reason": "not enough transactions"}

    df = pd.DataFrame(
        [
            {
                "id": row.id,
                "district": row.district,
                "area_ping": row.area_ping,
                "rent_per_ping": row.rent_per_ping,
            }
            for row in rows
        ]
    )

    scaled, scaling = _standardize_features(df)
    points = [scaled[i] for i in range(len(scaled))]
    centroids, assignments = run_mapreduce_kmeans(points, num_clusters=num_clusters)

    raw_centroids = []
    for centroid in centroids:
        area = centroid[0] * scaling["std"]["area_ping"] + scaling["mean"]["area_ping"]
        rent = (
            centroid[1] * scaling["std"]["rent_per_ping"]
            + scaling["mean"]["rent_per_ping"]
        )
        raw_centroids.append((float(area), float(rent)))

    labels = _label_clusters(raw_centroids)
    session.query(RentalCluster).delete()

    cluster_counts = pd.Series(assignments).value_counts().to_dict()
    for cluster_idx, (area, rent) in enumerate(raw_centroids):
        session.add(
            RentalCluster(
                cluster_id=cluster_idx,
                segment_label=labels[cluster_idx],
                centroid_area_ping=area,
                centroid_rent_per_ping=rent,
                sample_size=int(cluster_counts.get(cluster_idx, 0)),
                updated_at=datetime.utcnow(),
            )
        )

    return {
        "clusters": num_clusters,
        "assignments": len(assignments),
        "segments": labels,
        "updated_at": datetime.utcnow().isoformat(),
    }
