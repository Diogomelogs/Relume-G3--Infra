from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .types_basic import (
    InferredString,
    InferredDatetime,
    ProvenancedString,
    ProvenancedNumber,
    ProvenancedDatetime,
    ProvenancedDate,
    EvidenceNumber,
    ConfidenceState,
    EvidenceRef,
    InferenceMeta,
)

from .layer0 import (
    Layer0Custodia,
    IntegrityProof,
    ProcessingEvent,
    CustodyEvent,
    StorageURI,
    HashAlgorithm,
    StorageKind,
    DocumentSource,
    VersionEdge,
)
from .layer1 import Layer1, ArtefatoBruto
from .layer2 import Layer2Evidence
from .layer3 import Layer3Evidence
from .layer4_canonical import Layer4SemanticNormalization
from .layer6 import Layer6Optimization


class DocumentMemoryCanonical(BaseModel):
    """
    Contrato canônico v0.2.0 de DocumentMemory.

    - Sempre possui Layer0Custodia (identidade, integridade, custódia).
    - Pode ter, opcionalmente, as layers 1–6, dependendo do tipo de mídia
      e do quão longe o pipeline foi naquela instância.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    version: str = Field(
        default="v0.2.0",
        description="Versão do schema canônico de DocumentMemory.",
    )

    # ---------------------------
    # Layer 0 – Custódia
    # ---------------------------
    layer0: Layer0Custodia = Field(
        ...,
        description=(
            "Camada de custódia: identidade, integridade, cadeia de custódia "
            "e armazenamento."
        ),
    )

    # ---------------------------
    # Layer 1 – Mídia & artefatos
    # ---------------------------
    layer1: Optional[Layer1] = Field(
        default=None,
        description=(
            "Descrição da mídia (imagem, vídeo, áudio, documento) e artefatos "
            "físicos/técnicos."
        ),
    )

    # ---------------------------
    # Layer 2 – Extração determinística
    # ---------------------------
    layer2: Optional[Layer2Evidence] = Field(
        default=None,
        description=(
            "Atributos determinísticos extraídos (dimensões, EXIF, num_paginas, "
            "duracao, texto literal, etc.)."
        ),
    )

    # ---------------------------
    # Layer 3 – Inferência semântica local
    # ---------------------------
    layer3: Optional[Layer3Evidence] = Field(
        default=None,
        description=(
            "Inferências lógicas de nível de documento (tipo de evento, "
            "entidades semânticas, rótulos, etc.)."
        ),
    )

    # ---------------------------
    # Layer 4 – Normalização canônica global
    # ---------------------------
    layer4: Optional[Layer4SemanticNormalization] = Field(
        default=None,
        description=(
            "Normalização canônica de datas, locais, entidades e tags, com "
            "lastro explícito nas layers inferiores."
        ),
    )

    # ---------------------------
    # Layer 5 – Derivados
    # ---------------------------
    layer5: Optional[dict] = Field(
        default=None,
        description=(
            "Derivados de mídia (thumbnails, previews, versões OCRizadas, "
            "textos planos, etc.)."
        ),
    )

    # ---------------------------
    # Layer 6 – Indexação / Vetores
    # ---------------------------
    layer6: Optional[Layer6Optimization] = Field(
        default=None,
        description=(
            "Estratégia de indexação (BM25, vetorial) e vetores associados."
        ),
    )

    # ---------------------------
    # Helpers
    # ---------------------------

    @property
    def media_kind(self) -> Optional[str]:
        return getattr(self.layer1, "midia", None)

    @property
    def is_image(self) -> bool:
        return self.media_kind == "imagem"

    @property
    def is_video(self) -> bool:
        return self.media_kind == "video"

    @property
    def is_audio(self) -> bool:
        return self.media_kind == "audio"

    @property
    def is_document(self) -> bool:
        return self.media_kind == "documento"


# Aliases oficiais do contrato v0.2.0
DocumentMemory = DocumentMemoryCanonical
DocumentMemory_v0_2_0 = DocumentMemoryCanonical

__all__ = [
    "DocumentMemoryCanonical",
    "DocumentMemory",
    "DocumentMemory_v0_2_0",
    "Layer0Custodia",
    "IntegrityProof",
    "ProcessingEvent",
    "CustodyEvent",
    "StorageURI",
    "HashAlgorithm",
    "StorageKind",
    "DocumentSource",
    "VersionEdge",
    "Layer1",
    "ArtefatoBruto",
    "Layer2Evidence",
    "Layer3Evidence",
    "Layer4SemanticNormalization",
    "Layer6Optimization",
]

# ============================================================
# Pydantic v2 – Resolve forward references
# ============================================================

DocumentMemoryCanonical.model_rebuild()
DocumentMemory.model_rebuild()
DocumentMemory_v0_2_0.model_rebuild()