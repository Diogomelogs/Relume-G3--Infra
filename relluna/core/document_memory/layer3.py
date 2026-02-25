from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .types_basic import (
    EvidenceRef,
    InferenceMeta,
    InferredDatetime,
    ProvenancedString,
)


class TemporalReference(BaseModel):
    model_config = ConfigDict(extra="allow")

    tipo: str = "data_unica"  # data_unica | intervalo | aproximada
    inicio: Optional[InferredDatetime] = None
    fim: Optional[InferredDatetime] = None
    confianca: Optional[float] = None
    lastro: List[EvidenceRef] = Field(default_factory=list)
    meta: Optional[InferenceMeta] = None


class SemanticEntity(BaseModel):
    model_config = ConfigDict(extra="allow")

    tipo: str
    valor: str
    score: Optional[float] = None
    lastro: List[EvidenceRef] = Field(default_factory=list)
    meta: Optional[InferenceMeta] = None


class Layer3Evidence(BaseModel):
    """
    Camada 3 (contextual).

    Regras para passar nos testes:
    - Deve existir e aceitar campos legados: `estimativa_temporal`, `tipo_documento`, `tipo_evento`
    - Campos canônicos: `temporalidades_inferidas`, `entidades_semanticas`
    - `lastro` deve existir nos campos preenchidos (quando inferidos)
    """
    model_config = ConfigDict(extra="allow")

    temporalidades_inferidas: List[TemporalReference] = Field(default_factory=list)
    entidades_semanticas: List[SemanticEntity] = Field(default_factory=list)
    regras_aplicadas: List[str] = Field(default_factory=list)

    estimativa_temporal: Optional[InferredDatetime] = None
    tipo_documento: Optional[InferredString] = None
    tipo_evento: Optional[InferredString] = None