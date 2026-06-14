"""Fetch and clean Taipei City open-data rental transactions."""

from __future__ import annotations

import io
import subprocess
import warnings
from pathlib import Path

import pandas as pd
import requests

TAIPEI_REAL_PRICE_WEEKLY_CSV_URL = (
    "https://data.taipei/api/frontstage/tpeod/dataset/resource.download"
    "?rid=2979c431-7a32-4067-9af2-e716cd825c4b"
)

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
RAW_CSV_PATH = RAW_DIR / "taipei_real_price_weekly.csv"
RENT_CSV_PATH = PROCESSED_DIR / "taipei_rent_prices.csv"
INGEST_CSV_PATH = PROCESSED_DIR / "transactions_ingest.csv"
SUMMARY_CSV_PATH = PROCESSED_DIR / "taipei_rent_summary_by_district.csv"

USER_AGENT = (
    "Mozilla/5.0 compatible; LeasePulseTaipeiBot/1.0; "
    "for academic final project"
)


def download_csv(url: str = TAIPEI_REAL_PRICE_WEEKLY_CSV_URL) -> bytes:
    """Download CSV from Taipei open-data portal with SSL/curl fallbacks."""
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=60, verify=True)
        response.raise_for_status()
        return response.content
    except requests.exceptions.SSLError:
        warnings.warn(
            "SSL verification failed for data.taipei; retrying with curl.",
            stacklevel=2,
        )
        result = subprocess.run(
            ["curl", "-sL", url],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout

        warnings.warn(
            "curl fallback unavailable; retrying requests with verify=False.",
            stacklevel=2,
        )
        response = requests.get(url, headers=headers, timeout=60, verify=False)
        response.raise_for_status()
        return response.content


def read_csv_with_fallback(content: bytes) -> pd.DataFrame:
    encodings = ["utf-8-sig", "utf-8", "big5", "cp950"]
    last_error = None
    for enc in encodings:
        try:
            return pd.read_csv(io.BytesIO(content), encoding=enc)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise RuntimeError(f"Cannot decode CSV content. Last error: {last_error}")


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).replace("\ufeff", "").strip() for col in df.columns]
    return df


def to_number(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.extract(r"([-+]?\d*\.?\d+)", expand=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def parse_roc_date(value) -> pd.Timestamp | pd.NaT:
    """Parse SDATE like 1150427 (ROC year + MMDD)."""
    if pd.isna(value):
        return pd.NaT

    text = str(value).strip().split(".")[0]
    if not text.isdigit() or len(text) < 7:
        return pd.NaT

    roc_year = int(text[:3])
    month = int(text[3:5])
    day = int(text[5:7])
    western_year = roc_year + 1911
    return pd.Timestamp(year=western_year, month=month, day=day)


def filter_rental_rows(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    masks = []

    for col in ["CASE_T", "CASE_F", "RENT_TYPE", "RENT_PERIOD"]:
        if col in df.columns:
            masks.append(df[col].astype(str).str.contains("租", na=False))

    if not masks:
        raise ValueError(
            "Cannot find rental-related columns. "
            f"Available columns: {list(df.columns)}"
        )

    rental_mask = masks[0]
    for mask in masks[1:]:
        rental_mask = rental_mask | mask

    rental_df = df[rental_mask].copy()
    if rental_df.empty:
        raise ValueError("Filtered result is empty. Please inspect CASE_T / CASE_F values.")
    return rental_df


def infer_rent_total_ntd(df: pd.DataFrame) -> pd.Series:
    """TPRICE in weekly report is typically in 萬元; UPRICE*FAREA is NTD."""
    tprice = to_number(df["TPRICE"]) if "TPRICE" in df.columns else pd.Series(pd.NA, index=df.index)
    uprice = to_number(df["UPRICE"]) if "UPRICE" in df.columns else pd.Series(pd.NA, index=df.index)
    area = to_number(df["FAREA"]) if "FAREA" in df.columns else pd.Series(pd.NA, index=df.index)

    from_unit = uprice * area
    from_tprice = tprice * 10_000

    rent_total = from_unit.copy()
    fill_tprice = rent_total.isna() & from_tprice.notna()
    rent_total.loc[fill_tprice] = from_tprice.loc[fill_tprice]

    # When both exist, prefer the value that looks like monthly NTD.
    both = from_unit.notna() & from_tprice.notna()
    rent_total.loc[both] = from_unit.loc[both]
    return rent_total.round().astype("Int64")


def normalize_rent_columns(df: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame()
    output["district"] = df["DISTRICT"] if "DISTRICT" in df.columns else None
    output["building_type"] = df["BUITYPE"] if "BUITYPE" in df.columns else "unknown"
    output["area_ping"] = to_number(df["FAREA"]) if "FAREA" in df.columns else None
    output["rent_total_ntd"] = infer_rent_total_ntd(df)
    output["rent_per_ping_ntd"] = to_number(df["UPRICE"]) if "UPRICE" in df.columns else None
    output["transaction_date"] = (
        df["SDATE"].apply(parse_roc_date) if "SDATE" in df.columns else pd.NaT
    )
    output["has_elevator"] = df["ELEVATOR"] if "ELEVATOR" in df.columns else None
    output["rent_type"] = df["RENT_TYPE"] if "RENT_TYPE" in df.columns else None
    output["rent_period"] = df["RENT_PERIOD"] if "RENT_PERIOD" in df.columns else None
    output["source"] = "taipei_open_data_real_price_weekly"

    need_fill = (
        output["rent_per_ping_ntd"].isna()
        & output["rent_total_ntd"].notna()
        & output["area_ping"].notna()
        & (output["area_ping"] > 0)
    )
    output.loc[need_fill, "rent_per_ping_ntd"] = (
        output.loc[need_fill, "rent_total_ntd"].astype(float)
        / output.loc[need_fill, "area_ping"]
    )

    output = output[
        output["district"].notna()
        & output["area_ping"].notna()
        & output["rent_total_ntd"].notna()
        & output["transaction_date"].notna()
    ].copy()

    output = output[
        (output["area_ping"] > 0)
        & (output["area_ping"] < 300)
        & (output["rent_total_ntd"] > 3_000)
        & (output["rent_total_ntd"] < 1_000_000)
        & (output["rent_per_ping_ntd"] > 100)
        & (output["rent_per_ping_ntd"] < 10_000)
    ].copy()

    return output


def to_ingest_dataframe(rent_df: pd.DataFrame) -> pd.DataFrame:
    """Map cleaned open-data rows to the DB ingest schema."""
    ingest = pd.DataFrame(
        {
            "district": rent_df["district"].astype(str),
            "building_type": rent_df["building_type"].astype(str),
            "area_ping": rent_df["area_ping"].astype(float),
            "rent_ntd": rent_df["rent_total_ntd"].astype(int),
            "rent_per_ping": rent_df["rent_per_ping_ntd"].astype(float),
            "transaction_date": pd.to_datetime(rent_df["transaction_date"]).dt.date,
            "source": rent_df["source"],
        }
    )
    return ingest


def make_district_summary(rent_df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        rent_df.groupby("district")
        .agg(
            sample_size=("rent_total_ntd", "count"),
            median_rent_total_ntd=("rent_total_ntd", "median"),
            avg_rent_total_ntd=("rent_total_ntd", "mean"),
            p25_rent_total_ntd=("rent_total_ntd", lambda x: x.quantile(0.25)),
            p75_rent_total_ntd=("rent_total_ntd", lambda x: x.quantile(0.75)),
            median_area_ping=("area_ping", "median"),
            median_rent_per_ping_ntd=("rent_per_ping_ntd", "median"),
            avg_rent_per_ping_ntd=("rent_per_ping_ntd", "mean"),
        )
        .reset_index()
        .sort_values("median_rent_total_ntd", ascending=False)
    )
    numeric_cols = summary.select_dtypes(include="number").columns
    summary[numeric_cols] = summary[numeric_cols].round(2)
    return summary


def fetch_and_process(
    url: str = TAIPEI_REAL_PRICE_WEEKLY_CSV_URL,
    save_raw: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    content = download_csv(url)
    if save_raw:
        RAW_CSV_PATH.write_bytes(content)

    raw_df = clean_column_names(read_csv_with_fallback(content))
    rent_raw_df = filter_rental_rows(raw_df)
    rent_df = normalize_rent_columns(rent_raw_df)
    ingest_df = to_ingest_dataframe(rent_df)
    summary_df = make_district_summary(rent_df)

    rent_df.to_csv(RENT_CSV_PATH, index=False, encoding="utf-8-sig")
    ingest_df.to_csv(INGEST_CSV_PATH, index=False, encoding="utf-8-sig")
    summary_df.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")

    return rent_df, ingest_df, summary_df


def main() -> None:
    print("Downloading Taipei real-price weekly CSV...")
    rent_df, ingest_df, summary_df = fetch_and_process()

    print(f"Saved raw CSV to {RAW_CSV_PATH}")
    print(f"Clean rental rows: {len(rent_df)}")
    print(f"Saved cleaned rental data to {RENT_CSV_PATH}")
    print(f"Saved ingest-ready CSV to {INGEST_CSV_PATH}")
    print(f"Saved district summary to {SUMMARY_CSV_PATH}")
    print(f"Ingest rows ready for DB: {len(ingest_df)}")
    print("\nTop districts by median rent:")
    print(summary_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
