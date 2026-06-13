"""Ingest rental transaction data modeled on Taiwan MOI open-data fields."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

from pipeline.db import RentalTransaction, init_db, session_scope


def normalize_transactions(df: pd.DataFrame) -> pd.DataFrame:
    required = [
        "district",
        "building_type",
        "area_ping",
        "rent_ntd",
        "transaction_date",
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    cleaned = df.copy()
    cleaned["transaction_date"] = pd.to_datetime(cleaned["transaction_date"]).dt.date
    cleaned["area_ping"] = cleaned["area_ping"].astype(float)
    cleaned["rent_ntd"] = cleaned["rent_ntd"].astype(int)
    cleaned["rent_per_ping"] = cleaned["rent_ntd"] / cleaned["area_ping"]
    cleaned["floor"] = cleaned.get("floor", pd.Series([None] * len(cleaned)))
    cleaned["building_age_years"] = cleaned.get(
        "building_age_years", pd.Series([None] * len(cleaned))
    )
    cleaned["source"] = cleaned.get("source", "moi_open_data")
    return cleaned


def ingest_csv(csv_path: Path, replace: bool = True) -> int:
    init_db()
    df = normalize_transactions(pd.read_csv(csv_path))

    with session_scope() as session:
        if replace:
            session.query(RentalTransaction).delete()

        ingested = 0
        for _, row in df.iterrows():
            session.add(
                RentalTransaction(
                    district=row["district"],
                    building_type=row["building_type"],
                    area_ping=float(row["area_ping"]),
                    rent_ntd=int(row["rent_ntd"]),
                    rent_per_ping=float(row["rent_per_ping"]),
                    transaction_date=row["transaction_date"],
                    floor=int(row["floor"]) if pd.notna(row["floor"]) else None,
                    building_age_years=(
                        int(row["building_age_years"])
                        if pd.notna(row["building_age_years"])
                        else None
                    ),
                    source=str(row["source"]),
                    ingested_at=datetime.utcnow(),
                )
            )
            ingested += 1
    return ingested


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest rental transaction CSV")
    parser.add_argument(
        "--csv",
        default="data/sample/transactions.csv",
        help="Path to transaction CSV",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append records instead of replacing existing data",
    )
    args = parser.parse_args()

    count = ingest_csv(Path(args.csv), replace=not args.append)
    print(f"Ingested {count} rental transactions from {args.csv}")


if __name__ == "__main__":
    main()
