from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from enum import Enum


class MediaType(str, Enum):
    imagem = "imagem"
    audio = "audio"
    video = "video"
    documento = "documento"


class OriginType(str, Enum):
    digital_nativo = "digital_nativo"
    digitalizado = "digitalizado"
    hibrido = "hibrido"


class ArtefatoBruto(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    tipo: Optional[str] = None

    uri: str
    nome: Optional[str] = None
    mimetype: Optional[str] = None
    tamanho_bytes: Optional[int] = None
    created_at: Optional[datetime] = None

    # 🔹 necessário para compatibilidade com testes antigos
    metadados_nativos: Optional[dict] = None


class Layer1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    midia: MediaType
    origem: OriginType
    artefatos: list[ArtefatoBruto]