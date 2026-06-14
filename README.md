# LeasePulse Taipei

**LeasePulse Taipei** helps independent landlords in Taipei City price rental units using **live government open data**, district-level analytics, interactive rent quotes, and a subscription-ready API.

NTU Big Data Systems (Spring 2026) final project: *Design a System That Monetizes Data*.

## Code layout

| Path | Role |
|------|------|
| `data/taipei_open_data.py` | Download & clean Taipei City weekly real-price CSV |
| `data/ingest.py` | Load cleaned CSV into SQLite/PostgreSQL |
| `data/collect_ptt_forum_signals.py` | PTT rental-board crawl (last 2 years) |
| `data/collect_search_trends.py` | Google Trends rent-pricing keywords (24 months) |
| `data/collect_app_store_reviews.py` | App Store review pain points (last 2 years) |
| `data/collect_competitor_pricing.py` | Live competitor pricing pages |
| `data/collect_public_demand_evidence.py` | Aggregate all public demand signals |
| `scripts/*.py` | Thin CLI wrappers that call `data/` modules |
| `pipeline/processor.py` | District metrics + HW2 MapReduce K-Means |
| `api/main.py` / `dashboard/app.py` | FastAPI + Streamlit delivery |

Implementation lives in **`data/`**. The `scripts/` folder only provides command-line entry points for reproducibility.

## Data sources and reliability

| Source | Command (also in `make run`) | Output | Reliability | Caveats |
|--------|------------------------------|--------|-------------|---------|
| **Taipei City real-price CSV** | `make ingest` | `data/processed/transactions_ingest.csv` | **High** — official open data, weekly refresh | Delayed vs. listing sites; raw addresses not kept in DB |
| **PTT rental boards** | `make ptt` | `forum_signals_real.json` | **Medium** — live public posts, 2-year filter, PII redaction | Forum bias; qualitative demand signal only |
| **Google Trends** | `make search-trends` | `search_trends_real.json` | **Medium** — Google relative index (0–100) via public widget API | Not absolute search volume |
| **App Store reviews** | `make app-reviews` | `app_reviews_real.json` | **Medium** — Apple public RSS feed | App-user pain points, not landlord interviews |
| **Competitor pricing pages** | `make competitors` | `competitor_pricing_real.json` | **Medium** — live pages + manual verified prices + source URLs | Listing fees vary by plan; verify against source pages |
| **Combined evidence report** | `make public-evidence` | `demand_evidence_public_report.json` | Aggregates the above | No private interviews claimed |

Competitor URL list (591 listing fees + project pricing benchmark): `data/sources/competitor_pricing_sources.json`

**Submission zip:** always use `bash scripts/package_submission.sh final_clean.zip` — it excludes `.venv/`, `.git/`, caches, and local DB files.

Taipei open-data endpoint:

```
https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid=2979c431-7a32-4067-9af2-e716cd825c4b
```

## Quick start

```bash
git clone https://github.com/FettHsiao/bdfinal.git
cd bdfinal
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Runs ALL crawlers + evidence report + open-data ingest + batch processing
make run
make report

make api        # terminal 1
make dashboard  # terminal 2
```

### `make run` executes

1. `make ptt` — PTT crawl (last 2 years)
2. `make search-trends` — Google Trends (24 months)
3. `make app-reviews` — App Store reviews (last 2 years)
4. `make competitors` — competitor pricing pages
5. `make public-evidence` — aggregate into `demand_evidence_public_report.json`
6. `make ingest` — Taipei open-data fetch + DB load
7. `make process` — Pandas aggregates + HW2 K-Means

### Other commands

```bash
make fetch      # open-data download/clean only
make process    # recompute metrics
make test       # unit + smoke tests
make package    # clean zip without .venv/.git
```

## Ethics

- Public evidence only — no private interviews in the default pipeline
- Crawlers throttle requests, filter recency, redact phone/email/LINE where applicable
- Competitor and forum outputs include source URLs for verification
- Coursework/demo use only; review PDPA before commercial deployment

See [docs/architecture.md](docs/architecture.md).
