"""
Read model for causal timeline visualization.

Transforms CausalLink objects from Layer2 into a graph visualization
ready for frontend consumption, with event details from Layer3.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CausalTimelineEvent(BaseModel):
    """Probatory event for display in causal timeline."""

    event_id: str
    event_type: str
    title: str
    description: Optional[str] = None
    date_iso: str
    date_display: Optional[str] = None
    entities: Dict[str, Any]
    confidence: float


class CausalTimelineLink(BaseModel):
    """Causal link for graph visualization."""

    event_a_id: str
    event_b_id: str
    link_type: str = Field(description="presunção_legal|progressão_anatômica|etc")
    confidence: float = Field(ge=0.0, le=1.0)
    rule_id: str
    rule_explanation: str
    seta_cor: str = Field(description="Hex color code (#rrggbb)")
    seta_espessura: int = Field(ge=1, le=3, description="Thickness in pixels")
    review_state: str = Field(
        default="auto", description="auto|needs_review|human_confirmed"
    )
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_note: Optional[str] = None


class CausalTimeline(BaseModel):
    """Complete causal timeline for a document."""

    document_id: str
    document_type: Optional[str] = None
    date_document: Optional[str] = None
    eventos: List[CausalTimelineEvent]
    grafo: List[CausalTimelineLink]
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (total_events, total_links, confidence_avg, etc.)",
    )


def build_causal_timeline_from_dm(
    document_id: str, dm: Any
) -> Optional[CausalTimeline]:
    """
    Build causal timeline read model from DocumentMemory.

    Args:
        document_id: Document ID
        dm: DocumentMemory object

    Returns:
        CausalTimeline with events and causal links, or None if Layer3/Layer2 missing
    """
    if not dm or not dm.layer3 or not dm.layer2:
        return None

    # Extract events from Layer3
    eventos = []
    if dm.layer3.eventos_probatorios:
        for evt in dm.layer3.eventos_probatorios:
            # Parse ISO date for display
            date_display = None
            try:
                dt = datetime.fromisoformat(evt.date_iso)
                date_display = dt.strftime("%d/%m/%Y %H:%M")
            except (ValueError, AttributeError):
                date_display = evt.date_iso

            eventos.append(
                CausalTimelineEvent(
                    event_id=evt.event_id,
                    event_type=evt.event_type or "",
                    title=evt.title or "",
                    description=evt.description,
                    date_iso=evt.date_iso,
                    date_display=date_display,
                    entities=evt.entities or {},
                    confidence=evt.confidence or 0.0,
                )
            )

    # Extract causal links from Layer2.sinais_documentais["causal_link_v1"]
    links = []
    metadata: Dict[str, Any] = {
        "total_events": len(eventos),
        "total_links": 0,
        "confidence_avg": 0.0,
        "conflicts": 0,
        "strong_links": 0,
        "medium_links": 0,
        "weak_links": 0,
    }

    sinal = dm.layer2.sinais_documentais.get("causal_link_v1")
    if sinal and sinal.valor:
        import json

        try:
            links_json = json.loads(sinal.valor)
            confidences = []

            for link_dict in links_json:
                # Map internal representation to output model
                link = CausalTimelineLink(
                    event_a_id=link_dict.get("event_a_id", ""),
                    event_b_id=link_dict.get("event_b_id", ""),
                    link_type=link_dict.get("link_type", ""),
                    confidence=link_dict.get("confidence", 0.0),
                    rule_id=link_dict.get("rule_id", ""),
                    rule_explanation=link_dict.get("rule_explanation", ""),
                    seta_cor=link_dict.get("visual_color", "#6b7280"),
                    seta_espessura=link_dict.get("visual_thickness", 2),
                    review_state=link_dict.get("review_state", "auto"),
                    reviewed_by=link_dict.get("reviewed_by"),
                    reviewed_at=link_dict.get("reviewed_at"),
                    review_note=link_dict.get("review_note"),
                )
                links.append(link)
                confidences.append(link.confidence)

                # Update metadata
                if link.confidence == 0.0:
                    metadata["conflicts"] += 1
                elif link.confidence >= 0.8:
                    metadata["strong_links"] += 1
                elif link.confidence >= 0.6:
                    metadata["medium_links"] += 1
                else:
                    metadata["weak_links"] += 1

            metadata["total_links"] = len(links)
            if confidences:
                metadata["confidence_avg"] = sum(confidences) / len(confidences)

        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    return CausalTimeline(
        document_id=document_id,
        document_type=None,
        date_document=dm.layer0.ingestiontimestamp.isoformat()
        if dm.layer0 and dm.layer0.ingestiontimestamp
        else None,
        eventos=eventos,
        grafo=links,
        metadata=metadata,
    )
