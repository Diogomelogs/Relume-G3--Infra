"""
STATUS: morto

Este helper grava timeline em `layer6.timeline_events`, caminho que não é a
fonte oficial atual nem participa da timeline pública.

Mantido apenas como marcador explícito de legado para evitar reutilização
acidental durante a migração.
"""

def attach_timeline(document_memory, timeline):

    if "layer6" not in document_memory or document_memory["layer6"] is None:
        document_memory["layer6"] = {}

    document_memory["layer6"]["timeline_events"] = timeline

    return document_memory
