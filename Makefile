.PHONY: install setup run fetch ingest process evidence api dashboard report clean sample

PY ?= .venv/bin/python
export DATABASE_URL ?= sqlite:///data/leasepulse.db
export PYTHONPATH := $(CURDIR)

install:
	python3 -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -e .

setup: install evidence ingest process

evidence:
	$(PY) scripts/collect_demand_evidence.py

fetch:
	$(PY) -m data

ingest:
	$(PY) scripts/ingest_open_data.py --fetch

sample:
	$(PY) scripts/ingest_open_data.py --sample

process:
	$(PY) -m pipeline.processor

run: evidence ingest process

api:
	$(PY) -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

dashboard:
	API_BASE_URL=http://localhost:8000 $(PY) -m streamlit run dashboard/app.py

report:
	$(PY) report/generate_report.py

clean:
	rm -f data/leasepulse.db
	rm -rf data/processed
