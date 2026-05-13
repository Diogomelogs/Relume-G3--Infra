from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Derivado(BaseModel):
    tipo: str
    uri: str


class StorageURI(BaseModel):
    uri: str
    kind: str = "blob"


class Layer5Derivatives(BaseModel):
    imagens_derivadas: List[Derivado] = Field(default_factory=list)
    videos_derivados: List[Derivado] = Field(default_factory=list)
    audios_derivados: List[Derivado] = Field(default_factory=list)
    documentos_derivados: List[Derivado] = Field(default_factory=list)
    storage_uris: List[StorageURI] = Field(default_factory=list)
    persistence_state: Optional[str] = None

    # ── Read models oficiais para frontend (P0.2) ──────────────────────
    read_models: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Read models pré-computados para frontend (timeline_v1, entity_summary_v1, etc.).",
    )