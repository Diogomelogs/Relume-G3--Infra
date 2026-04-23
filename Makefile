.PHONY: setup test benchmark benchmark-gate api lint format smoke

PYTHON ?= python3
PIP ?= pip3
PYTEST ?= pytest
PYTHONDONTWRITEBYTECODE ?= 1

setup:
	$(PIP) install -e ".[dev]"

test:
	PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTEST) -q

benchmark:
	PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/benchmark_runner.py

benchmark-gate:
	PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) scripts/benchmark_runner.py --gate-critical

api:
	uvicorn relluna.services.ingestion.api:app --reload --host 0.0.0.0 --port 8000

lint:
	ruff check .

format:
	ruff format .

smoke:
	PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) tools/debug_pipeline_trace.py
