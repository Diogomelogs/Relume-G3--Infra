from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EntityRef(BaseModel):
    kind: str  # "pessoa" | "org" | "local" | "objeto" ...
    label: str
    confidence: Optional[float] = None


class TimelinePanelRef(BaseModel):
    endpoint: str
    total_events: int = 0
    anchored_events: int = 0
    timeline_consistency_score: Optional[float] = None


class DocumentReadModel(BaseModel):
    """
    Read Model do painel (materialized view).
    Regra: derivado do DocumentMemory + síntese (título/resumo).
    Rebuildável a qualquer momento.
    """

    model_config = ConfigDict(extra="forbid")

    document_id: str

    media_type: str  # MediaType.value (mantemos string para não acoplar demais)

    # UX
    title: str
    summary: str

    # tempo
    date_canonical: Optional[str] = None  # ISO date "YYYY-MM-DD" ou datetime ISO se precisar
    period_label: Optional[str] = None    # ex: "2008", "2008-10", "2008-10-22"

    # organização
    doc_type: Optional[str] = None        # DocumentType.value (taxonomia)
    tags: List[str] = Field(default_factory=list)
    entities: List[EntityRef] = Field(default_factory=list)
    event_types: List[str] = Field(default_factory=list)
    patient: Optional[str] = None
    provider: Optional[str] = None
    cids: List[str] = Field(default_factory=list)

    # links rápidos p/ artefatos (raw, thumb, derived etc)
    artefacts: Dict[str, str] = Field(default_factory=dict)
    timeline: Optional[TimelinePanelRef] = None

    # indicadores operacionais/semânticos
    confidence_indicators: Dict[str, Any] = Field(default_factory=dict)
    needs_review_count: int = 0

    created_at: datetime
    updated_at: datetime

    # índice de texto (para busca fulltext / fallback)
    search_text: str = ""
