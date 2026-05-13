from __future__ import annotations

import warnings

from relluna.core.document_memory import DocumentMemory
from relluna.services.deterministic_extractors.basic import extract_basic
from relluna.services.context_inference.basic import infer_layer3
from relluna.services.correlation.layer4 import apply_layer4
from relluna.services.derivatives.layer5 import apply_layer5


def run_basic_pipeline(dm: DocumentMemory) -> DocumentMemory:
    """
    Wrapper legado.

    O caminho vivo do produto passa por `relluna.services.ingestion.api`.
    Este pipeline é mantido apenas por compatibilidade com código/testes antigos.
    """
    warnings.warn(
        "relluna.core.basic_pipeline é legado; use o fluxo da API em "
        "relluna.services.ingestion.api.",
        DeprecationWarning,
        stacklevel=2,
    )
    dm = extract_basic(dm)
    dm = infer_layer3(dm)
    dm = apply_layer4(dm)
    dm = apply_layer5(dm)

    return dm
