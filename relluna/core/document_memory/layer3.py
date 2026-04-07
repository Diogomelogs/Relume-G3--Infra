from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .types_basic import (
    EvidenceRef,
    InferenceMeta,
    InferredDatetime,
    InferredString,
)
from .transcription import TranscriptionSegment


class TemporalReference(BaseModel):
    model_config = ConfigDict(extra="allow")

    tipo: str = "data_unica"
    inicio: Optional[InferredDatetime] = None
    fim: Optional[InferredDatetime] = None
    confianca: Optional[float] = None
    provenance_status: Optional[str] = None
    review_state: Optional[str] = None
    lastro: List[EvidenceRef] = Field(default_factory=list)
    meta: Optional[InferenceMeta] = None


class SemanticEntity(BaseModel):
    model_config = ConfigDict(extra="allow")

    tipo: str
    valor: str
    score: Optional[float] = None
    normalizado: Optional[str] = None
    review_state: Optional[str] = None
    lastro: List[EvidenceRef] = Field(default_factory=list)
    meta: Optional[InferenceMeta] = None


class ContextualTranscription(BaseModel):
    model_config = ConfigDict(extra="allow")

    engine: str
    metodo: str
    texto: Optional[str] = None
    segmentos: List[TranscriptionSegment] = Field(default_factory=list)
    confianca: Optional[float] = None
    lastro: List[EvidenceRef] = Field(default_factory=list)
    meta: Optional[InferenceMeta] = None


class ProbatoryEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Novo layout rico
    event_id: Optional[str] = None
    event_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    date_iso: Optional[str] = None
    entities: Dict[str, Any] = Field(default_factory=dict)
    citations: List[EvidenceRef] = Field(default_factory=list)
    confidence: Optional[float] = None
    review_state: Optional[str] = None
    provenance_status: Optional[str] = None
    derivation_rule: Optional[str] = None
    contradiction_candidates: List[Dict[str, Any]] = Field(default_factory=list)

    # Compat legada
    tipo_evento: Optional[InferredString] = None
    descricao_curta: Optional[str] = None
    evidencias_origem: List[EvidenceRef] = Field(default_factory=list)
    justificativa: Optional[str] = None
    confianca: Optional[float] = None
    meta: Optional[InferenceMeta] = None


class PageContextClassification(BaseModel):
    model_config = ConfigDict(extra="allow")

    pagina: int
    classificacao: str
    confianca: Optional[float] = None
    taxonomy_source: Optional[str] = None
    taxonomy_confidence: Optional[float] = None
    evidencias_origem: List[EvidenceRef] = Field(default_factory=list)
    meta: Optional[InferenceMeta] = None


class Layer3Evidence(BaseModel):
    """
    Camada 3 (contextual).
    Deve conter apenas inferências, classificações e composições contextuais
    derivadas da Layer2, nunca fatos inventados.
    """
    model_config = ConfigDict(extra="allow")

    temporalidades_inferidas: List[TemporalReference] = Field(default_factory=list)
    entidades_semanticas: List[SemanticEntity] = Field(default_factory=list)
    regras_aplicadas: List[str] = Field(default_factory=list)

    classificacoes_pagina: List[PageContextClassification] = Field(default_factory=list)
    eventos_probatorios: List[ProbatoryEvent] = Field(default_factory=list)
    transcricao_contextual: Optional[ContextualTranscription] = None

    # legados
    estimativa_temporal: Optional[InferredDatetime] = None
    tipo_documento: Optional[InferredString] = None
    tipo_evento: Optional[InferredString] = None