# Architecture

## Product

LeasePulse Taipei converts rental transaction data into pricing intelligence for independent landlords managing 2–15 units in Greater Taipei.

## Data sources

| Source | Type | Role |
|--------|------|------|
| MOI-style transaction CSV | Batch ingest | Ground-truth rent levels by district and building type |
| Landlord interviews | Qualitative | Willingness-to-pay and workflow pain points |
| Public forum coding | Qualitative | Problem frequency and language used by target users |
| Competitor benchmarks | Desk research | Pricing anchors and feature gaps |

Production scaling would add scheduled pulls from Taiwan's government open-data APIs and licensed listing feeds.

## Storage

- **Primary store:** PostgreSQL in production; SQLite for local/demo
- **Why:** Structured relational facts (transactions, aggregates) with indexed district queries
- **ORM:** SQLAlachemy models in `pipeline/db.py`

## Processing

- **Paradigm:** Batch ETL after each ingest window (nightly or weekly)
- **District analytics:** Pandas aggregations (`median`, percentile bands)
- **Market segmentation:** HW2 MapReduce K-Means on `(area_ping, rent_per_ping)` via `pipeline/mapreduce_kmeans.py`
- **Outputs:** `district_metrics`, `pricing_recommendations`, `rental_clusters`

## Delivery

1. **Streamlit dashboard** — primary SMB user interface
2. **FastAPI** — programmatic quotes and integration path for small property managers
3. **Future:** email/Line alerts for vacancy-risk thresholds (message queue stub via Redis in compose file)

## End-to-end flow

```
┌─────────────┐   ┌──────────────┐   ┌─────────────────┐
│ CSV / API   │──►│ ingest script│──►│ SQL store       │
└─────────────┘   └──────────────┘   └────────┬────────┘
                                              │
                                              ▼
                                     ┌─────────────────┐
                                     │ batch processor │
                                     └────────┬────────┘
                                              │
                         ┌────────────────────┼────────────────────┐
                         ▼                    ▼                    ▼
                  district metrics    recommendations        cache (Redis)
                         │                    │
                         └──────────► FastAPI ◄┘
                                           │
                                           ▼
                                    Streamlit UI
```

## Scalability sketch

| Scale | Transactions | Approach | Est. monthly infra |
|-------|--------------|----------|--------------------|
| MVP | 30–500 | SQLite / small Postgres, Pandas | < USD 25 |
| 10× | 5k | Partitioned Postgres, indexed materialized views | USD 80–150 |
| 100× | 50k+ | Spark batch on object storage, read replicas | USD 400–800 |

## Security & compliance

- No personal tenant identifiers stored in MVP dataset
- PDPA/GDPR review required before collecting landlord PII at scale
- Respect robots.txt and platform ToS for any future listing scrape
