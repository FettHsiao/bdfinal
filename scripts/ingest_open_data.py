"""Ingest rental transaction data from Taipei open data or local CSV."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse

import pandas as pd

from data.taipei_open_data import INGEST_CSV_PATH, fetch_and_process
from pipeline.db import RentalTransaction, init_db, session_scope


def normalize_transactions(df: pd.DataFrame) -> pd.DataFrame:
    if "rent_ntd" not in df.columns and "rent_total_ntd" in df.columns:
        df = df.rename(columns={"rent_total_ntd": "rent_ntd"})
    if "rent_per_ping" not in df.columns and "rent_per_ping_ntd" in df.columns:
        df = df.rename(columns={"rent_per_ping_ntd": "rent_per_ping"})

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
    if "rent_per_ping" not in cleaned.columns or cleaned["rent_per_ping"].isna().all():
        cleaned["rent_per_ping"] = cleaned["rent_ntd"] / cleaned["area_ping"]
    else:
        cleaned["rent_per_ping"] = cleaned["rent_per_ping"].astype(float)

    cleaned["floor"] = cleaned["floor"] if "floor" in cleaned.columns else None
    cleaned["building_age_years"] = (
        cleaned["building_age_years"] if "building_age_years" in cleaned.columns else None
    )
    cleaned["source"] = cleaned.get("source", "taipei_open_data_real_price_weekly")
    return cleaned


def ingest_dataframe(df: pd.DataFrame, replace: bool = True) -> int:
    init_db()
    cleaned = normalize_transactions(df)

    with session_scope() as session:
        if replace:
            session.query(RentalTransaction).delete()

        ingested = 0
        for _, row in cleaned.iterrows():
            session.add(
                RentalTransaction(
                    district=row["district"],
                    building_type=row["building_type"],
                    area_ping=float(row["area_ping"]),
                    rent_ntd=int(row["rent_ntd"]),
                    rent_per_ping=float(row["rent_per_ping"]),
                    transaction_date=row["transaction_date"],
                    floor=int(row["floor"]) if pd.notna(row.get("floor")) else None,
                    building_age_years=(
                        int(row["building_age_years"])
                        if pd.notna(row.get("building_age_years"))
                        else None
                    ),
                    source=str(row["source"]),
                    ingested_at=datetime.utcnow(),
                )
            )
            ingested += 1
    return ingested


def ingest_csv(csv_path: Path, replace: bool = True) -> int:
    return ingest_dataframe(pd.read_csv(csv_path), replace=replace)


def fetch_and_ingest(replace: bool = True) -> dict:
    _, ingest_df, summary_df = fetch_and_process()
    count = ingest_dataframe(ingest_df, replace=replace)
    return {
        "ingested": count,
        "ingest_csv": str(INGEST_CSV_PATH),
        "districts": int(summary_df["district"].nunique()),
        "source": "taipei_open_data_real_price_weekly",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest rental transaction data")
    parser.add_argument(
        "--csv",
        default=None,
        help="Path to transaction CSV (defaults to Taipei open-data fetch)",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Download latest Taipei open-data CSV before ingest",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use bundled sample CSV instead of live open data",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append records instead of replacing existing data",
    )
    args = parser.parse_args()

    replace = not args.append

    if args.sample:
        csv_path = Path(args.csv or "data/sample/transactions.csv")
        count = ingest_csv(csv_path, replace=replace)
        print(f"Ingested {count} rental transactions from {csv_path}")
        return

    if args.fetch or args.csv is None:
        summary = fetch_and_ingest(replace=replace)
        print(
            "Ingested {ingested} live rental transactions from Taipei open data "
            "({districts} districts)".format(**summary)
        )
        print(f"Ingest CSV saved to {summary['ingest_csv']}")
        return

    count = ingest_csv(Path(args.csv), replace=replace)
    print(f"Ingested {count} rental transactions from {args.csv}")


if __name__ == "__main__":
    main()
