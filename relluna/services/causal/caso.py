"""
Caso multi-documento: agrega múltiplos DocumentMemory em um caso causal unificado.

Consolida timelines de vários documentos, aplica nexo causal inter-documento,
e produz um grafo causal único para o caso.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from relluna.core.document_memory import DocumentMemory, ProbatoryEvent
from relluna.services.causal.engine import infer_causal_links, _parse_date
from relluna.services.causal.types import CausalLink


@dataclass
class Caso:
    """Agregação de múltiplos DocumentMemory em um caso jurídico."""

    case_id: str
    title: Optional[str] = None
    documents: List[DocumentMemory] = field(default_factory=list)
    merged_events: List[ProbatoryEvent] = field(default_factory=list)
    causal_links: List[CausalLink] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_document(self, dm: DocumentMemory) -> None:
        self.documents.append(dm)

    def build(self) -> "Caso":
        """Consolida timeline e infere nexo causal inter-documento."""
        self.merged_events = merge_timelines(self.documents)
        self.causal_links = infer_cross_document_links(self.documents)
        self.metadata = {
            "total_documents": len(self.documents),
            "total_events": len(self.merged_events),
            "total_links": len(self.causal_links),
            "document_ids": [
                dm.layer0.documentid for dm in self.documents if dm.layer0
            ],
        }
        return self


def merge_timelines(documents: List[DocumentMemory]) -> List[ProbatoryEvent]:
    """
    Merge de eventos probatórios de múltiplos documentos.

    Dedup por event_id, ordena por data.
    """
    seen_ids: set = set()
    merged: List[ProbatoryEvent] = []

    for dm in documents:
        if not dm.layer3 or not dm.layer3.eventos_probatorios:
            continue
        for evt in dm.layer3.eventos_probatorios:
            key = evt.event_id or id(evt)
            if key in seen_ids:
                continue
            seen_ids.add(key)
            merged.append(evt)

    merged.sort(key=lambda e: _parse_date(e.date_iso))
    return merged


def infer_cross_document_links(documents: List[DocumentMemory]) -> List[CausalLink]:
    """
    Infere nexo causal usando eventos de todos os documentos.

    Cria um DocumentMemory virtual com todos os eventos mesclados,
    depois aplica o motor Kausal padrão.
    """
    if not documents:
        return []

    merged = merge_timelines(documents)
    if not merged:
        return []

    base_dm = documents[0]

    from relluna.core.document_memory import Layer3Evidence

    virtual_dm = DocumentMemory(
        layer0=base_dm.layer0,
        layer1=base_dm.layer1,
        layer2=base_dm.layer2,
        layer3=Layer3Evidence(eventos_probatorios=merged),
    )

    return infer_causal_links(virtual_dm)


__all__ = ["Caso", "merge_timelines", "infer_cross_document_links"]
