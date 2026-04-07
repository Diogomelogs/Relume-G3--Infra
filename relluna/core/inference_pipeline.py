from __future__ import annotations

from relluna.core.document_memory import DocumentMemory, Layer3Evidence
from relluna.services.inference import llm_context


def run_inference_pipeline(dm: DocumentMemory) -> DocumentMemory:
    # garante existência de Layer3
    if dm.layer3 is None:
        dm.layer3 = Layer3Evidence()

    # Chamada via módulo, para permitir monkeypatch de llm_context.infer_layer3_from_layer2
    dm.layer3 = llm_context.infer_layer3_from_layer2(dm)
    return dm
