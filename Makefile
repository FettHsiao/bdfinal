.PHONY: install setup run fetch ingest process \
	ptt search-trends app-reviews competitors public-evidence public-evidence-collect \
	api dashboard report clean test package

PY ?= .venv/bin/python
export DATABASE_URL ?= sqlite:///data/leasepulse.db
export PYTHONPATH := $(CURDIR)

install:
	python3 -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -e .

setup: install run

# Individual collectors (implementation lives under data/)
ptt:
	$(PY) -m data.collect_ptt_forum_signals --taipei-only --max-pages 4 --sleep 1.0 --since-years 2

search-trends:
	$(PY) -m data.collect_search_trends

app-reviews:
	$(PY) -m data.collect_app_store_reviews --since-years 2

competitors:
	$(PY) -m data.collect_competitor_pricing

public-evidence-collect: ptt search-trends app-reviews competitors

public-evidence: public-evidence-collect
	$(PY) -m data.collect_public_demand_evidence

fetch:
	$(PY) -m data.taipei_open_data

ingest:
	$(PY) -m data.ingest --fetch

process:
	$(PY) -m pipeline.processor

# Full pipeline: all crawlers + evidence report + open-data ingest + batch processing
run: public-evidence ingest process

api:
	$(PY) -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

dashboard:
	API_BASE_URL=http://localhost:8000 $(PY) -m streamlit run dashboard/app.py

report:
	$(PY) report/generate_report.py

test:
	$(PY) -m unittest discover -s tests -p "test_*.py"

package:
	bash scripts/package_submission.sh

clean:
	rm -f data/leasepulse.db
	rm -rf data/processed
