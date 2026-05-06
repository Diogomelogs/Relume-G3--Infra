from __future__ import annotations

import warnings

from relluna.core.document_memory import DocumentMemory, Layer3Evidence
from relluna.services.context_inference import llm_context


def run_inference_pipeline(dm: DocumentMemory) -> DocumentMemory:
    warnings.warn(
        "relluna.core.inference_pipeline é legado; use o fluxo da API em "
        "relluna.services.ingestion.api.",
        DeprecationWarning,
        stacklevel=2,
    )
    # garante existência de Layer3
    if dm.layer3 is None:
        dm.layer3 = Layer3Evidence()

    # Chamada via módulo, para permitir monkeypatch de llm_context.infer_layer3_from_layer2
    dm.layer3 = llm_context.infer_layer3_from_layer2(dm)
    return dm
