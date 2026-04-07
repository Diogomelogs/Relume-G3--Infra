from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class ConfidenceState(str, Enum):
    confirmado = "confirmado"
    inferido = "inferido"
    insuficiente = "insuficiente"
    negado = "negado"
    estimado = "estimado"


class ReviewState(str, Enum):
    auto_confirmed = "auto_confirmed"
    review_recommended = "review_recommended"
    needs_review = "needs_review"


class EvidenceRef(BaseModel):
    """Referência leve para evidência/lastro."""
    model_config = ConfigDict(extra="allow")

    kind: Optional[str] = None
    uri: Optional[str] = None
    page: Optional[int] = None
    span: Optional[List[int]] = None

    # Proveniência visual
    bbox: Optional[List[float]] = None
    snippet: Optional[str] = None
    source_path: Optional[str] = None

    # Comentários / notas
    note: Optional[str] = None

    # Confiança e revisão
    confidence: Optional[float] = None
    provenance_status: Optional[str] = None
    review_state: Optional[str] = None


class InferenceMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    engine: str = "rules"
    version: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())


class ProvenancedString(BaseModel):
    model_config = ConfigDict(extra="allow")

    valor: Optional[str] = None
    fonte: str = "unknown"
    metodo: str = "unknown"
    estado: ConfidenceState = ConfidenceState.insuficiente
    confianca: Optional[float] = None
    review_state: Optional[str] = None
    confidence_reason: List[str] = Field(default_factory=list)
    lastro: List[EvidenceRef] = Field(default_factory=list)


class ProvenancedNumber(BaseModel):
    model_config = ConfigDict(extra="allow")

    valor: Optional[float] = None
    fonte: str = "unknown"
    metodo: str = "unknown"
    estado: ConfidenceState = ConfidenceState.insuficiente
    confianca: Optional[float] = None
    lastro: List[EvidenceRef] = Field(default_factory=list)


class ProvenancedDatetime(BaseModel):
    model_config = ConfigDict(extra="allow")

    valor: Optional[datetime] = None
    fonte: str = "unknown"
    metodo: str = "unknown"
    estado: ConfidenceState = ConfidenceState.insuficiente
    confianca: Optional[float] = None
    lastro: List[EvidenceRef] = Field(default_factory=list)


# Tipos "Inferred*" são aliases semânticos (mantêm compat com imports legados)
InferredString = ProvenancedString
InferredDatetime = ProvenancedDatetime
EvidenceNumber = ProvenancedNumber
ProvenancedDate = ProvenancedDatetime  # compat legada


class GpsExif(BaseModel):
    model_config = ConfigDict(extra="allow")

    lat: Optional[ProvenancedNumber] = None
    lon: Optional[ProvenancedNumber] = None


class MetadadosExif(BaseModel):
    """
    Container completo de metadados EXIF de imagens.
    Apenas campos presentes no arquivo são preenchidos.
    """
    model_config = ConfigDict(extra="allow")

    # Device / Câmera
    fabricante: Optional[ProvenancedString] = None  # Make (Apple, Canon, Sony...)
    modelo_camera: Optional[ProvenancedString] = None  # Camera model
    modelo_lente: Optional[ProvenancedString] = None  # Lens model

    # Configurações de captura
    iso: Optional[ProvenancedNumber] = None  # ISO speed
    abertura: Optional[ProvenancedString] = None  # FNumber (f/2.8)
    velocidade_obturador: Optional[ProvenancedString] = None  # ExposureTime (1/250s)
    distancia_focal: Optional[ProvenancedString] = None  # FocalLength (35mm)
    distancia_focal_35mm: Optional[ProvenancedNumber] = None  # FocalLengthIn35mmFilm

    # Data/Horário
    data_captura: Optional[ProvenancedString] = None  # DateTimeOriginal
    data_modificacao: Optional[ProvenancedString] = None  # DateTime
    data_digitizacao: Optional[ProvenancedString] = None  # DateTimeDigitized

    # GPS
    gps: Optional[GpsExif] = None

    # Software / Processamento
    software: Optional[ProvenancedString] = None  # Software usado
    processamento: Optional[ProvenancedString] = None  # ImageDescription

    # Orientação e dimensões técnicas
    orientacao: Optional[ProvenancedNumber] = None  # Orientation (1-8)
    resolucao_x: Optional[ProvenancedNumber] = None  # XResolution DPI
    resolucao_y: Optional[ProvenancedNumber] = None  # YResolution DPI

    # Flash e iluminação
    flash: Optional[ProvenancedString] = None  # Flash mode
    brancos: Optional[ProvenancedString] = None  # WhiteBalance

    # Metadados de copyright
    direitos_autor: Optional[ProvenancedString] = None  # Copyright
    artista: Optional[ProvenancedString] = None  # Artist


class QualidadeSinal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolucao: Optional[ProvenancedString] = None
    foco: Optional[ProvenancedNumber] = None
    iluminacao: Optional[ProvenancedNumber] = None
    nitidez: Optional[ProvenancedNumber] = None


class EntidadeVisualObjetiva(BaseModel):
    model_config = ConfigDict(extra="allow")

    label: str
    score: Optional[float] = None


# ============================================================
# v0.2.0 – Modelo forte de entidade semântica
# ============================================================

class SemanticEntity(BaseModel):
    model_config = ConfigDict(extra="allow")

    tipo: str
    valor: str
    fonte: str
    confianca: float

    # Campos preparados para evolução futura
    normalizado: Optional[str] = None


class TemporalReference(BaseModel):
    valor: str = Field(..., description="Data inferida")
    fonte: str = "inferido"
    metodo: str = "ocr_context"
    estado: str = "inferido"
    confianca: float = 0.8
    lastro: Optional[list] = None


EvidenceAnchor = EvidenceRef  # Alias para compatibilidade