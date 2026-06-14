#!/usr/bin/env bash
# Run the full LeasePulse pipeline. Equivalent to: make run
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export DATABASE_URL="${DATABASE_URL:-sqlite:///data/leasepulse.db}"
export PYTHONPATH="$ROOT"

PY="${PY:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
fi

mkdir -p data/processed

echo "==> 1/7 PTT forum signals (last 2 years)"
"$PY" -m data.collect_ptt_forum_signals --taipei-only --max-pages 4 --sleep 1.0 --since-years 2

echo "==> 2/7 Google Trends (24 months)"
"$PY" -m data.collect_search_trends

echo "==> 3/7 App Store reviews (last 2 years)"
"$PY" -m data.collect_app_store_reviews --since-years 2

echo "==> 4/7 Competitor pricing pages"
"$PY" -m data.collect_competitor_pricing

echo "==> 5/7 Public demand evidence report"
"$PY" -m data.collect_public_demand_evidence

echo "==> 6/7 Fetch + ingest Taipei open data"
"$PY" -m data.ingest --fetch

echo "==> 7/7 Batch processing + HW2 K-Means"
"$PY" -m pipeline.processor

echo "Done. Start services with: make api && make dashboard"
