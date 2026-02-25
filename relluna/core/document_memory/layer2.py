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


class Layer2Evidence(BaseModel):
    """
    Camada de evidência técnica determinística.
    NÃO deve usar tipos primitivos.
    Mantém rastreabilidade (lastro) para Layer3 e auditoria.
    """

    # Permitir campos adicionais durante pipeline
    model_config = ConfigDict(extra="allow")

    # =====================================================
    # IMAGEM
    # =====================================================
    largura_px: Optional[ProvenancedNumber] = None
    altura_px: Optional[ProvenancedNumber] = None

    # =====================================================
    # DOCUMENTO
    # =====================================================
    num_paginas: Optional[ProvenancedNumber] = None
    texto_ocr_literal: Optional[ProvenancedString] = None

    # =====================================================
    # ÁUDIO / VÍDEO
    # =====================================================
    duracao_segundos: Optional[ProvenancedNumber] = None
    taxa_amostragem_hz: Optional[ProvenancedNumber] = None

    # =====================================================
    # EXIF
    # =====================================================
    data_exif: Optional[ProvenancedString] = None
    gps_exif: Optional[GpsExif] = None

    # =====================================================
    # QUALIDADE DE SINAL
    # =====================================================
    qualidade_sinal: Optional[QualidadeSinal] = None

    # =====================================================
    # VISUAL / OCR
    # =====================================================
    entidades_visuais_objetivas: List[EntidadeVisualObjetiva] = Field(default_factory=list)
    ocr_texto: Optional[ProvenancedString] = None

    # =====================================================
    # OUTROS SINAIS
    # =====================================================
    sinais_documentais: Dict[str, str] = Field(default_factory=dict)
    # --- Transcrição (áudio/vídeo) ---
    transcricao_literal: Optional[ProvenancedString] = None
    transcricao_segmentada: list[TranscriptionSegment] = []
    num_falantes: Optional[int] = None
