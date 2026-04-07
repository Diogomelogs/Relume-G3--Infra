from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


CHUNK_SIZE = 8192


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def compute_contentfingerprint_from_file(path: Union[str, Path]) -> str:
    """
    SHA-256 completo do arquivo (hex 64).
    """
    h = hashlib.sha256()
    file_path = Path(path)

    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            if not chunk:
                break
            h.update(chunk)

    return h.hexdigest()


def compute_contentfingerprint_from_bytes(data: bytes) -> str:
    """
    SHA-256 completo do buffer em memória.
    """
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


class IntegrityProof(BaseModel):
    """
    Prova de integridade: como o hash foi produzido e quando.
    """
    model_config = ConfigDict(extra="forbid")

    created_at: datetime = Field(default_factory=utcnow)
    kind: Literal["local_signature", "external_signature", "timestamp_authority"] = "local_signature"
    payload: Dict[str, Any] = Field(default_factory=dict)

    @staticmethod
    def local_sha256(hash_hex: str) -> "IntegrityProof":
        return IntegrityProof(
            kind="local_signature",
            payload={"algoritmo": "sha256", "hash": hash_hex},
        )


class CustodyEvent(BaseModel):
    """
    Evento de cadeia de custódia.
    """
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime = Field(default_factory=utcnow)
    etapa: str
    agente: str
    acao: Literal[
        "ingest",
        "store_original",
        "normalize",
        "derive",
        "move",
        "copy",
        "delete_logical",
        "export",
    ]
    origem_uri: Optional[str] = None
    destino_uri: Optional[str] = None
    detalhes: Dict[str, Any] = Field(default_factory=dict)


class ProcessingEvent(BaseModel):
    """
    Evento técnico de processamento.
    """
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime = Field(default_factory=utcnow)
    etapa: str
    engine: str
    status: Literal["success", "warning", "error"] = "success"
    detalhes: Dict[str, Any] = Field(default_factory=dict)


class VersionEdge(BaseModel):
    """
    Relação de versionamento/derivação entre artefatos.
    """
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime = Field(default_factory=utcnow)
    from_artifact_id: str
    to_artifact_id: str
    relation: Literal[
        "normalized_from",
        "preview_of",
        "frame_of",
        "transcript_of",
        "ocr_payload_of",
        "derived_from",
    ]
    method: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class Layer0Custodia(BaseModel):
    """
    Camada 0: custódia + integridade.
    Deve ser um snapshot da ingestão.
    """
    model_config = ConfigDict(extra="forbid")

    documentid: str
    contentfingerprint: str
    fingerprint_algorithm: Literal["sha256"] = "sha256"

    ingestiontimestamp: datetime = Field(default_factory=utcnow)
    ingestionagent: str

    original_filename: Optional[str] = None
    mimetype: Optional[str] = None
    size_bytes: Optional[int] = None

    authenticitystate: Optional[str] = None
    juridicalreadinesslevel: Optional[int] = 0

    custodychain: List[CustodyEvent] = Field(default_factory=list)
    processingevents: List[ProcessingEvent] = Field(default_factory=list)
    versiongraph: List[VersionEdge] = Field(default_factory=list)

    integrityproofs: List[IntegrityProof] = Field(default_factory=list)

    @field_validator("contentfingerprint")
    @classmethod
    def _validate_sha256_hex(cls, v: str) -> str:
        vv = (v or "").strip().lower()
        if len(vv) != 64:
            raise ValueError("contentfingerprint deve ser sha256 hex (64 chars).")
        int(vv, 16)
        return vv

    @field_validator("ingestiontimestamp")
    @classmethod
    def _validate_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("ingestiontimestamp deve ser timezone-aware (UTC).")
        return v

    @field_validator("size_bytes")
    @classmethod
    def _validate_size_bytes(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("size_bytes não pode ser negativo.")
        return v

    @field_validator("juridicalreadinesslevel")
    @classmethod
    def _validate_juridicalreadinesslevel(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("juridicalreadinesslevel não pode ser negativo.")
        return v

    @field_validator("authenticitystate", mode="before")
    @classmethod
    def _normalize_authenticitystate(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        vv = v.strip()
        return vv or None

    @field_validator("custodychain", mode="before")
    @classmethod
    def _coerce_custodychain(cls, v: Any) -> Any:
        if v is None:
            return []
        if not isinstance(v, list):
            raise TypeError("custodychain deve ser lista.")
        coerced: List[CustodyEvent] = []
        for item in v:
            if isinstance(item, CustodyEvent):
                coerced.append(item)
            elif isinstance(item, dict):
                coerced.append(CustodyEvent.model_validate(item))
            else:
                raise TypeError("custodychain deve conter CustodyEvent ou dict compatível.")
        return coerced

    @field_validator("processingevents", mode="before")
    @classmethod
    def _coerce_processingevents(cls, v: Any) -> Any:
        if v is None:
            return []
        if not isinstance(v, list):
            raise TypeError("processingevents deve ser lista.")
        coerced: List[ProcessingEvent] = []
        for item in v:
            if isinstance(item, ProcessingEvent):
                coerced.append(item)
            elif isinstance(item, dict):
                legacy = dict(item)
                legacy.setdefault("status", "success")
                legacy.setdefault("detalhes", {})
                coerced.append(ProcessingEvent.model_validate(legacy))
            else:
                raise TypeError("processingevents deve conter ProcessingEvent ou dict compatível.")
        return coerced

    @field_validator("versiongraph", mode="before")
    @classmethod
    def _coerce_versiongraph(cls, v: Any) -> Any:
        if v is None:
            return []
        if not isinstance(v, list):
            raise TypeError("versiongraph deve ser lista.")
        coerced: List[VersionEdge] = []
        for item in v:
            if isinstance(item, VersionEdge):
                coerced.append(item)
            elif isinstance(item, dict):
                coerced.append(VersionEdge.model_validate(item))
            else:
                raise TypeError("versiongraph deve conter VersionEdge ou dict compatível.")
        return coerced

    @field_validator("integrityproofs", mode="before")
    @classmethod
    def _coerce_integrityproofs(cls, v: Any) -> Any:
        if v is None:
            return []
        if not isinstance(v, list):
            raise TypeError("integrityproofs deve ser lista.")
        coerced: List[IntegrityProof] = []
        for item in v:
            if isinstance(item, IntegrityProof):
                coerced.append(item)
            elif isinstance(item, dict):
                coerced.append(IntegrityProof.model_validate(item))
            else:
                raise TypeError("integrityproofs deve conter IntegrityProof ou dict compatível.")
        return coerced


Layer0 = Layer0Custodia