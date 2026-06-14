# Architecture

## Product

LeasePulse Taipei converts **live Taipei City open-data rental transactions** into pricing intelligence for independent landlords.

## Data sources

| Source | Type | Role |
|--------|------|------|
| Taipei Data Platform weekly real-price CSV | Live HTTP download | Primary transaction ground truth |
| Landlord interviews | Qualitative | Willingness-to-pay and workflow pain points |
| Public forum coding | Qualitative | Problem frequency and language used by target users |
| Competitor benchmarks | Desk research | Pricing anchors and feature gaps |

Download endpoint (official open data):

`https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid=2979c431-7a32-4067-9af2-e716cd825c4b`

Implementation: `data/taipei_open_data.py`

## Storage

- **Primary store:** PostgreSQL in production; SQLite for local/demo
- **ORM:** SQLAlchemy models in `pipeline/db.py`
- **Raw archive:** `data/raw/taipei_real_price_weekly.csv`
- **Processed files:** `data/processed/transactions_ingest.csv`

## Processing

- **Ingestion:** `scripts/ingest_open_data.py --fetch`
- **District analytics:** Pandas aggregations (`median`, percentile bands)
- **Market segmentation:** HW2 MapReduce K-Means on `(area_ping, rent_per_ping)`
- **Outputs:** `district_metrics`, `pricing_recommendations`, `rental_clusters`

## Delivery

1. **Streamlit dashboard** — district charts, quotes, K-Means segments
2. **FastAPI** — `/quote`, `/metrics/districts`, `/clusters`
3. **Future:** alerts via Redis pub/sub (stub in Docker Compose)

## End-to-end flow

```
Taipei open-data CSV
        │
        ▼
data/taipei_open_data.py  (download, filter 租賃, normalize)
        │
        ▼
scripts/ingest_open_data.py ──► SQL store
        │
        ▼
pipeline/processor.py (Pandas + HW2 K-Means)
        │
        ▼
FastAPI ──► Streamlit
```

## Scalability sketch

| Scale | Transactions | Approach | Est. monthly infra |
|-------|--------------|----------|--------------------|
| MVP | ~600 live rows | SQLite, Pandas, weekly cron fetch | < USD 25 |
| 10× | 5k | Postgres, materialized views | USD 80–150 |
| 100× | 50k+ | Spark batch, read replicas | USD 400–800 |

## Security & compliance

- Official open-data only in MVP (no private platform scraping)
- Addresses from raw CSV are not persisted in the product DB schema
- PDPA review required before commercial use
