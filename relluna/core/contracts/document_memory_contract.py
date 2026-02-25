from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Derivado(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: str
    uri: str


class StorageURI(BaseModel):
    """
    URI já persistida (ex.: Azure Blob), com metadados mínimos.
    """
    model_config = ConfigDict(extra="forbid")

    uri: str
    kind: Optional[str] = None


class Layer5Derivatives(BaseModel):
    """
    Contrato canônico de derivados (camada 5).
    """
    model_config = ConfigDict(extra="forbid")

    imagens_derivadas: List[Derivado] = Field(default_factory=list)
    audios_derivados: List[Derivado] = Field(default_factory=list)
    videos_derivados: List[Derivado] = Field(default_factory=list)
    documentos_derivados: List[Derivado] = Field(default_factory=list)

    # IMPORTANTES para os testes e2e/contratos
    storage_uris: List[StorageURI] = Field(default_factory=list)
    persistence_state: Optional[str] = None