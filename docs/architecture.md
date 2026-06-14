# Architecture

## Product

LeasePulse Taipei converts **live Taipei City open-data rental transactions** into pricing intelligence for independent landlords.

## Code organization

- **`data/`** — all data acquisition and ingestion logic (open data, crawlers, evidence aggregation)
- **`scripts/`** — thin CLI wrappers (`python scripts/foo.py` or `python -m data.foo`)
- **`pipeline/`** — batch analytics and HW2 MapReduce K-Means
- **`app/`** — FastAPI application (`app/main.py`)
- **`api/index.py`** — Vercel serverless entry (copies seed SQLite to `/tmp`)

## Data sources

| Source | Module | Reliability |
|--------|--------|-------------|
| Taipei Data Platform weekly CSV | `data/taipei_open_data.py` | High (official open data) |
| PTT rental boards | `data/collect_ptt_forum_signals.py` | Medium (public forum signal) |
| Google Trends | `data/collect_search_trends.py` | Medium (relative index via public widget API) |
| App Store RSS | `data/collect_app_store_reviews.py` | Medium (public reviews) |
| Competitor pages | `data/collect_competitor_pricing.py` | Medium-low (manual verify) |

## End-to-end flow (`make run`)

```
make ptt + search-trends + app-reviews + competitors
        │
        ▼
data/collect_public_demand_evidence.py ──► demand_evidence_public_report.json
        │
        ▼
data/taipei_open_data.py + data/ingest.py ──► SQL store
        │
        ▼
pipeline/processor.py (Pandas + HW2 K-Means)
        │
        ▼
FastAPI ──► Streamlit (local / Streamlit Cloud)
```

Deploy the API on Vercel via `api/index.py` + `vercel.json`; the seed database lives in `data/leasepulse.db`.

## Security & compliance

- Official open-data for transaction ground truth
- Public demand evidence only; no private interviews in default pipeline
- Crawlers use throttling, recency filters, and PII redaction where applicable
