#!/usr/bin/env bash
# Run the full LeasePulse pipeline from the project root.
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

echo "==> 1/3 Demand evidence"
"$PY" scripts/collect_demand_evidence.py

echo "==> 2/3 Ingest transactions"
"$PY" scripts/ingest_open_data.py --csv data/sample/transactions.csv

echo "==> 3/3 Batch processing + HW2 K-Means segmentation"
"$PY" -m pipeline.processor

echo "Done. Start services with:"
echo "  uvicorn api.main:app --reload --port 8000"
echo "  API_BASE_URL=http://localhost:8000 streamlit run dashboard/app.py"
