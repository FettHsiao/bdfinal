#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export DATABASE_URL="${DATABASE_URL:-sqlite:///data/leasepulse.db}"
export PYTHONPATH="$ROOT"

python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt

mkdir -p data/processed

python scripts/collect_demand_evidence.py
python scripts/ingest_open_data.py --csv data/sample/transactions.csv
python -m pipeline.processor

echo "Starting API on http://localhost:8000"
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

sleep 2
echo "Starting dashboard on http://localhost:8501"
streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0

kill "$API_PID" 2>/dev/null || true
