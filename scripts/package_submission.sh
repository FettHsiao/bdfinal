#!/usr/bin/env bash
# Create a clean submission zip without local virtualenvs or caches.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OUTPUT="${1:-leasepulse-final.zip}"

echo "Cleaning local artifacts..."
rm -rf .venv __pycache__ .pytest_cache .mypy_cache dist build *.egg-info leasepulse_taipei.egg-info
find . -name "__pycache__" -type d -prune -exec rm -rf {} +
find . -name "*.egg-info" -type d -prune -exec rm -rf {} +
find . -name ".DS_Store" -delete

echo "Creating ${OUTPUT}..."
zip -r "$OUTPUT" . \
  -x ".git/*" \
  -x ".venv/*" \
  -x "**/__pycache__/*" \
  -x "**/.pytest_cache/*" \
  -x "**/.DS_Store" \
  -x "**/__MACOSX/*" \
  -x "**/*.egg-info/*" \
  -x "data/leasepulse.db" \
  -x "data/raw/*" \
  -x "*.zip"

echo "Done: ${OUTPUT}"
