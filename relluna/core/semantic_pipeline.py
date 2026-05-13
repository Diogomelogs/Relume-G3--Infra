from __future__ import annotations

import warnings

from relluna.core.document_memory import DocumentMemory, Layer6Optimization
from relluna.infra.azure_openai import client as aoai  # importa módulo, não a função


def run_semantic_pipeline(dm: DocumentMemory) -> DocumentMemory:
    warnings.warn(
        "relluna.core.semantic_pipeline é legado; use o fluxo da API em "
        "relluna.services.ingestion.api.",
        DeprecationWarning,
        stacklevel=2,
    )
    if dm.layer6 is None:
        dm.layer6 = Layer6Optimization()

    # Exemplo: prioriza OCR literal como texto base
    base_text = None
    if dm.layer2 and getattr(dm.layer2, "texto_ocr_literal", None):
        base_text = dm.layer2.texto_ocr_literal.valor

    if not base_text:
        # nada para embedar; mantém layer6 como está
        return dm

    # Chamada via módulo → monkeypatch de aoai.embed_text funciona
    vec = aoai.embed_text(base_text)
    dm.layer6.embeddings_base = vec
    return dm
