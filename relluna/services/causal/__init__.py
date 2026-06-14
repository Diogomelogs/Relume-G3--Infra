"""
Kausal: motor de inferência de nexo causal previdenciário.

Implementa regras jurídicas (Lei 8.213/91, Decreto 3.048/99, CEREST) para
gerar hipóteses de nexo causal entre eventos probatórios em documentos
médico-jurídicos brasileiros.
"""

from relluna.services.causal.engine import infer_causal_links, persist_causal_links_to_layer2
from relluna.services.causal.types import CausalLink, CAUSAL_LINK_V1_SCHEMA
from relluna.services.causal.caso import Caso, merge_timelines, infer_cross_document_links
from relluna.services.causal.anti_nexo import apply_anti_nexo

__all__ = [
    "CausalLink",
    "CAUSAL_LINK_V1_SCHEMA",
    "infer_causal_links",
    "persist_causal_links_to_layer2",
    "Caso",
    "merge_timelines",
    "infer_cross_document_links",
    "apply_anti_nexo",
]
