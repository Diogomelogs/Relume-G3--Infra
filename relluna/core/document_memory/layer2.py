from __future__ import annotations

from typing import Optional, List, Dict

from pydantic import BaseModel, Field, ConfigDict

from relluna.core.document_memory.transcription import TranscriptionSegment
from .types_basic import (
    ProvenancedNumber,
    ProvenancedString,
    GpsExif,
    QualidadeSinal,
    EntidadeVisualObjetiva,
)


class PdfMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pdf_version: Optional[ProvenancedString] = None
    is_encrypted: Optional[ProvenancedString] = None
    producer: Optional[ProvenancedString] = None
    creator: Optional[ProvenancedString] = None
    creation_date: Optional[ProvenancedString] = None
    mod_date: Optional[ProvenancedString] = None
    linearized: Optional[ProvenancedString] = None


class MediaTechnicalMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    container: Optional[ProvenancedString] = None
    codec: Optional[ProvenancedString] = None
    bitrate: Optional[ProvenancedNumber] = None

    frame_rate: Optional[ProvenancedNumber] = None
    width_px: Optional[ProvenancedNumber] = None
    height_px: Optional[ProvenancedNumber] = None

    sample_rate_hz: Optional[ProvenancedNumber] = None
    channels: Optional[ProvenancedNumber] = None


class Layer2Evidence(BaseModel):
    """
    Camada de evidência técnica determinística.
    Deve conter apenas fatos observáveis, validados ou calculados diretamente
    do artefato por regra objetiva.

    Compatibilidade:
    - Mantém campos antigos de transcrição, mas o pipeline novo não deve mais
      escrever neles.
    """
    model_config = ConfigDict(extra="allow")

    # IMAGEM
    largura_px: Optional[ProvenancedNumber] = None
    altura_px: Optional[ProvenancedNumber] = None

    # DOCUMENTO
    num_paginas: Optional[ProvenancedNumber] = None
    texto_ocr_literal: Optional[ProvenancedString] = None
    pdf_metadata: Optional[PdfMetadata] = None

    # ÁUDIO / VÍDEO
    duracao_segundos: Optional[ProvenancedNumber] = None
    taxa_amostragem_hz: Optional[ProvenancedNumber] = None
    media_metadata: Optional[MediaTechnicalMetadata] = None

    # EXIF
    data_exif: Optional[ProvenancedString] = None
    gps_exif: Optional[GpsExif] = None

    # QUALIDADE DE SINAL
    qualidade_sinal: Optional[QualidadeSinal] = None

    # VISUAL / OCR
    entidades_visuais_objetivas: List[EntidadeVisualObjetiva] = Field(default_factory=list)
    ocr_texto: Optional[ProvenancedString] = None

    # SINAIS DETERMINÍSTICOS ESTRUTURADOS
    # Ex.: hard_entities_v2, layout_spans_v2, page_evidence_v1, timeline_seed_v2
    sinais_documentais: Dict[str, ProvenancedString] = Field(default_factory=dict)

    # -------------------------------
    # LEGADO / DEPRECATED
    # -------------------------------
    # Mantidos para compatibilidade de leitura de documentos antigos.
    # O pipeline novo não deve escrever mais nesses campos.
    transcricao_literal: Optional[ProvenancedString] = None
    transcricao_segmentada: List[TranscriptionSegment] = Field(default_factory=list)
    num_falantes: Optional[ProvenancedNumber] = None