# LeasePulse Taipei

**LeasePulse Taipei** is a data product that helps independent landlords in Greater Taipei price rental units using district-level transaction analytics, interactive rent quotes, and a subscription-ready API.

This repository supports the NTU Big Data Systems (Spring 2026) final project: *Design a System That Monetizes Data*.

## Project layout

| Path | Role |
|------|------|
| `scripts/ingest_open_data.py` | **Ingestion** — load rental CSV into the database |
| `pipeline/processor.py` | **Batch processing** — district metrics + pricing bands |
| `pipeline/mapreduce_kmeans.py` | **HW2 MapReduce K-Means** — market segmentation |
| `api/main.py` | **Delivery (API)** — FastAPI endpoints consumed by the dashboard |
| `dashboard/app.py` | **Delivery (UI)** — Streamlit product demo |
| `hw2/` | Original Homework 2 MapReduce K-Means submission |

## Architecture overview

```
CSV / open data
      │
      ▼
scripts/ingest_open_data.py ──► SQLite / PostgreSQL
      │
      ▼
pipeline/processor.py
  ├─ Pandas district aggregates
  └─ HW2 MapReduce K-Means (pipeline/mapreduce_kmeans.py)
      │
      ▼
api/main.py (FastAPI) ──► dashboard/app.py (Streamlit)
```

See [docs/architecture.md](docs/architecture.md) and [docs/hw2_integration.md](docs/hw2_integration.md).

## Quick start

**Important:** run commands from the project root (`final/`), not from inside `scripts/`.

```bash
cd "/Users/mac/Documents/電機碩一下/bd/final"
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# one-shot pipeline
make run
# or: bash scripts/run_all.sh

# start API (terminal 1)
make api

# start dashboard (terminal 2)
make dashboard
```

### Why `ModuleNotFoundError: No module named 'pipeline'` happens

Python only finds packages on `PYTHONPATH` or after `pip install -e .`.
If you run `python scripts/ingest_open_data.py` without installing, older shells may still fail — use either:

```bash
pip install -e .
python scripts/ingest_open_data.py
```

or:

```bash
export PYTHONPATH="$(pwd)"
python scripts/ingest_open_data.py
```

The scripts now also auto-insert the project root into `sys.path`.

## API endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /metrics/districts` | District rent statistics |
| `GET /recommendations` | Precomputed pricing bands |
| `GET /quote?district=...&building_type=...&area_ping=...` | Interactive rent quote |
| `GET /clusters` | HW2 K-Means market segments |
| `POST /admin/reprocess` | Re-run batch pipeline |

Interactive docs: http://localhost:8000/docs

## HW2 connection

Your `hw2/` folder contains MapReduce K-Means (`mapper.py`, `reducer.py`, `main.py`).
The final project reuses that design in `pipeline/mapreduce_kmeans.py` to segment rentals by
`(area_ping, rent_per_ping)` after ingestion. This satisfies the course expectation to build on
prior homework tooling in the processing layer.

## Docker

```bash
docker compose up --build
```

## Report

```bash
make report
# output: r14921059.pdf
```

Update `GITHUB_URL` in `report/generate_report.py` before submission.
