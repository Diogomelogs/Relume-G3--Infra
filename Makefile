.PHONY: setup test benchmark benchmark-gate api lint format

PYTHON ?= python3
PIP ?= pip3
PYTEST ?= pytest
PYTHONDONTWRITEBYTECODE ?= 1
LINT_TARGETS ?= relluna tests scripts tools

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
	ruff check $(LINT_TARGETS)

format:
	ruff format .
