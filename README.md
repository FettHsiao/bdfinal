# LeasePulse Taipei

**LeasePulse Taipei** helps independent landlords in Taipei City price rental units using **live government open data**, district-level analytics, interactive rent quotes, and a subscription-ready API.

NTU Big Data Systems (Spring 2026) final project: *Design a System That Monetizes Data*.

## Project layout

| Path | Role |
|------|------|
| `data/taipei_open_data.py` | **Live data acquisition** — download & clean Taipei City weekly real-price CSV |
| `scripts/ingest_open_data.py` | **Ingestion** — fetch open data and load into SQLite/PostgreSQL |
| `pipeline/processor.py` | **Batch processing** — district metrics + pricing bands |
| `pipeline/mapreduce_kmeans.py` | **HW2 MapReduce K-Means** — market segmentation |
| `api/main.py` | **Delivery (API)** — FastAPI endpoints |
| `dashboard/app.py` | **Delivery (UI)** — Streamlit dashboard |
| `hw2/` | Original Homework 2 MapReduce K-Means submission |

## Data source (real, not sample)

The pipeline downloads the official **Taipei City weekly real-price report** from the Taipei Data Platform:

```
https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid=2979c431-7a32-4067-9af2-e716cd825c4b
```

Processing steps (`python -m data`):

1. Download CSV (requests, with curl/SSL fallback for macOS Python SSL issues)
2. Filter rental rows (`CASE_T = 租賃`)
3. Normalize units: `TPRICE` in 萬元, `UPRICE` in NTD/ping, `SDATE` ROC date → ISO date
4. Save:
   - `data/raw/taipei_real_price_weekly.csv`
   - `data/processed/taipei_rent_prices.csv`
   - `data/processed/transactions_ingest.csv`
   - `data/processed/taipei_rent_summary_by_district.csv`

## Architecture

```
Taipei open-data API
        │
        ▼
data/taipei_open_data.py
        │
        ▼
scripts/ingest_open_data.py ──► SQLite / PostgreSQL
        │
        ▼
pipeline/processor.py
  ├─ Pandas district aggregates
  └─ HW2 MapReduce K-Means
        │
        ▼
api/main.py ──► dashboard/app.py
```

See [docs/architecture.md](docs/architecture.md) and [docs/hw2_integration.md](docs/hw2_integration.md).

## Quick start

Run from the project root (`final/`):

```bash
cd "/Users/mac/Documents/電機碩一下/bd/final"
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Download live Taipei data + ingest + process
make run

# terminal 1
make api

# terminal 2
make dashboard
```

### Useful commands

```bash
make fetch      # download & clean open data only
make ingest     # fetch + load DB (default)
make sample     # use bundled demo CSV instead
make process    # recompute metrics / K-Means
make report     # regenerate r14921059.pdf
```

### Import errors

If you see `ModuleNotFoundError: No module named 'pipeline'`:

```bash
pip install -e .
# or
export PYTHONPATH="$(pwd)"
```

Scripts also auto-add the project root to `sys.path`.

## API endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /metrics/districts` | District rent statistics |
| `GET /recommendations` | Precomputed pricing bands |
| `GET /quote?district=...&building_type=...&area_ping=...` | Interactive rent quote |
| `GET /clusters` | HW2 K-Means market segments |
| `POST /admin/reprocess` | Re-run batch pipeline |

Docs: http://localhost:8000/docs

## Report

```bash
make run
make report
```

Output: `r14921059.pdf` — update `GITHUB_URL` in `report/generate_report.py` before submission.

## Ethics & compliance

- Uses **official Taipei City open data**, not scraped private listing sites
- Raw addresses exist in the open CSV but are not stored in the product database schema
- For coursework/demo only; review PDPA before any commercial deployment
