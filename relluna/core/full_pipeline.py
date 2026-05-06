from __future__ import annotations

import warnings

from relluna.core import (
    basic_pipeline,
    inference_pipeline,
    canonical_pipeline,
    archival_pipeline,
    semantic_pipeline,
)
from relluna.core.document_memory import DocumentMemory

PIPE_STAGES = ("basic", "plus", "canonical", "archival", "full")


def run_full_pipeline(dm: DocumentMemory, *, stage: str = "full") -> DocumentMemory:
    warnings.warn(
        "relluna.core.full_pipeline é legado; use o fluxo da API em "
        "relluna.services.ingestion.api.",
        DeprecationWarning,
        stacklevel=2,
    )
    if stage not in PIPE_STAGES:
        raise ValueError(f"stage inválido: {stage}. Use {PIPE_STAGES}")

    # -> Layer2
    dm = basic_pipeline.run_basic_pipeline(dm)

    if stage in ("plus", "canonical", "archival", "full"):
        # -> Layer3 (LLM)
        dm = inference_pipeline.run_inference_pipeline(dm)

    if stage in ("canonical", "archival", "full"):
        # -> Layer4
        dm = canonical_pipeline.run_canonical_pipeline(dm)

    if stage in ("archival", "full"):
        # -> Layer5
        dm = archival_pipeline.run_archival_pipeline(dm)

    if stage == "full":
        # -> Layer6
        dm = semantic_pipeline.run_semantic_pipeline(dm)

    return dm
