from __future__ import annotations

from relluna.core.document_memory import DocumentMemory

def run_archival_pipeline(dm: DocumentMemory) -> DocumentMemory:
    # Se Layer5 não existir como model forte, use dict (extra allow) em models_v0_2_0
    if getattr(dm, "layer5", None) is None:
        dm.layer5 = {}  # mínimo real: estrutura para derivados/organização

    # Exemplo real mínimo:
    # - classificar em “coleção” por ano/mês (a partir de layer4.data_canonica)
    l4 = getattr(dm, "layer4", None)
    if l4 and getattr(l4, "data_canonica", None):
        dm.layer5["bucket_temporal"] = str(l4.data_canonica)[:7]  # YYYY-MM

    return dm