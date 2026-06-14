#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH="$ROOT"
export DATABASE_URL="${DATABASE_URL:-postgresql://leasepulse:leasepulse@postgres:5432/leasepulse}"

echo "==> ingest live Taipei open data"
python -m data.ingest --fetch

echo "==> batch processing + K-Means"
python -m pipeline.processor

echo "==> bootstrap complete"
