from __future__ import annotations

from relluna.core.document_memory import DocumentMemory
from relluna.services.deterministic_extractors.basic import extract_basic
from relluna.services.context_inference.basic import infer_layer3
from relluna.services.correlation.layer4 import apply_layer4
from relluna.services.derivatives.layer5 import apply_layer5


def run_basic_pipeline(dm: DocumentMemory) -> DocumentMemory:
    """
    Pipeline mínimo estável:
    Layer2 -> Layer3 -> Layer4 -> Layer5
    """
    dm = extract_basic(dm)
    dm = infer_layer3(dm)
    dm = apply_layer4(dm)
    dm = apply_layer5(dm)

    return dm