from __future__ import annotations

from relluna.core.document_memory import DocumentMemory


FONTE = "services.legal.legal_pipeline_v2"


def apply_legal_extraction(dm: DocumentMemory) -> DocumentMemory:
    """
    Layer2 não deve receber classificação jurídica nem canonização contextual.

    Esta etapa permanece como hook de compatibilidade do pipeline de extração,
    mas não grava mais sinais interpretativos na Layer2.

    A classificação de tipo documental e a composição contextual devem ocorrer
    em Layer3 via `infer_layer3`.
    """
    return dm
