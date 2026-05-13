.PHONY: setup test benchmark benchmark-gate api lint format smoke

PYTHON ?= python3
PIP ?= pip3
PYTEST ?= pytest
PYTHONDONTWRITEBYTECODE ?= 1
LINT_TARGETS ?= \
	relluna/services/ingestion/api.py \
	relluna/services/context_inference \
	relluna/services/derivatives \
	relluna/services/read_model \
	relluna/services/legal/legal_pipeline.py \
	relluna/services/persistence/dm_writer.py \
	relluna/services/transcription \
	relluna/core/document_memory/models.py \
	relluna/core/basic_pipeline.py \
	relluna/core/inference_pipeline.py \
	relluna/core/canonical_pipeline.py \
	relluna/core/archival_pipeline.py \
	relluna/core/semantic_pipeline.py \
	relluna/core/full_pipeline.py

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

smoke:
	PYTHONDONTWRITEBYTECODE=$(PYTHONDONTWRITEBYTECODE) $(PYTHON) tools/debug_pipeline_trace.py
