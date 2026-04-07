from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MediaType(str, Enum):
    imagem = "imagem"
    audio = "audio"
    video = "video"
    documento = "documento"


class OriginType(str, Enum):
    """
    Origem com granularidade defensável.
    """
    digital_nativo = "digital_nativo"
    digitalizado_analogico = "digitalizado_analogico"
    digitalizado_digital = "digitalizado_digital"
    hibrido = "hibrido"


class ArtefatoTipo(str, Enum):
    original = "original"
    normalized_for_pipeline = "normalized_for_pipeline"
    preview = "preview"
    frame_chave = "frame_chave"
    transcript = "transcript"
    ocr_payload = "ocr_payload"


class StorageKind(str, Enum):
    local_fs = "local_fs"
    azure_blob = "azure_blob"
    s3 = "s3"
    gcs = "gcs"
    memory = "memory"
    external = "external"


class PipelineRole(str, Enum):
    source_of_truth = "source_of_truth"
    pipeline_input = "pipeline_input"
    derived_evidence = "derived_evidence"
    user_preview = "user_preview"
    machine_payload = "machine_payload"


class ArtefatoBruto(BaseModel):
    """
    Um artefato é um arquivo físico original ou derivado.
    """
    model_config = ConfigDict(extra="allow")

    id: str
    tipo: ArtefatoTipo

    uri: str
    nome: Optional[str] = None
    mimetype: Optional[str] = None
    tamanho_bytes: Optional[int] = None
    created_at: datetime = Field(default_factory=utcnow)

    fingerprint_algorithm: Literal["sha256"] = "sha256"
    hash_sha256: Optional[str] = None

    metadados_nativos: Optional[Dict[str, Any]] = None

    # Enriquecimento não destrutivo
    storage_kind: Optional[StorageKind] = None
    is_persisted: bool = True
    derivado_de: Optional[str] = None
    pipeline_role: Optional[PipelineRole] = None
    normalization_applied: Optional[Dict[str, Any]] = None

    @field_validator("hash_sha256")
    @classmethod
    def _validate_sha256_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        vv = v.strip().lower()
        if len(vv) != 64:
            raise ValueError("hash_sha256 deve ser sha256 hex (64 chars).")
        int(vv, 16)
        return vv

    @field_validator("tamanho_bytes")
    @classmethod
    def _validate_tamanho_bytes(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("tamanho_bytes não pode ser negativo.")
        return v


class Layer1(BaseModel):
    """
    Camada 1: descrição e inventário de artefatos.
    """
    model_config = ConfigDict(extra="forbid")

    midia: MediaType
    origem: OriginType
    artefatos: list[ArtefatoBruto]

    @field_validator("artefatos")
    @classmethod
    def _validate_has_original(cls, v: list[ArtefatoBruto]) -> list[ArtefatoBruto]:
        if not v:
            raise ValueError("Layer1.artefatos não pode ser vazio.")
        if not any(a.tipo == ArtefatoTipo.original for a in v):
            raise ValueError("Layer1.artefatos deve conter ao menos 1 artefato tipo=original.")
        return v