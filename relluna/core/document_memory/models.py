from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional
from relluna.core.document_memory.layer3 import Layer3Evidence
from .layer4_front import Layer4SemanticNormalization as Layer4Evidence
from relluna.core.document_memory.layer4_canonical import Layer4SemanticNormalization

from pydantic import BaseModel, Field


class MediaType(str, Enum):
    imagem = "imagem"
    video = "video"
    audio = "audio"
    documento = "documento"


class OriginType(str, Enum):
    digital_nativo = "digital_nativo"
    digitalizado_analogico = "digitalizado_analogico"


class Layer0Custodia(BaseModel):
    documentid: str
    contentfingerprint: str
    ingestiontimestamp: datetime
    ingestionagent: str


class ArtefatoBruto(BaseModel):
    id: str
    tipo: str
    uri: str
    metadados_nativos: Dict[str, str] = Field(default_factory=dict)


class Layer1Artefatos(BaseModel):
    midia: MediaType
    origem: OriginType
    artefatos: List[ArtefatoBruto]


class ConfidenceState(str, Enum):
    confirmado = "confirmado"
    inferido = "inferido"
    insuficiente = "insuficiente"


class ProvenancedString(BaseModel):
    valor: Optional[str] = None
    fonte: str
    metodo: str
    estado: ConfidenceState
    confianca: Optional[float] = None


class ProvenancedNumber(BaseModel):
    valor: Optional[float] = None
    fonte: str
    metodo: str
    estado: ConfidenceState
    confianca: Optional[float] = None


class Layer2Evidence(BaseModel):
    data_exif: Optional[ProvenancedString] = None
    largura_px: Optional[ProvenancedNumber] = None
    altura_px: Optional[ProvenancedNumber] = None
    num_paginas: Optional[ProvenancedNumber] = None
    duracao_segundos: Optional[ProvenancedNumber] = None


class DocumentMemory(BaseModel):
    version: str = "v0.1.0"
    layer0: Layer0Custodia
    layer1: Layer1Artefatos
    layer2: Optional[Layer2Evidence] = None
    layer3: Optional[Layer3Evidence] = None

class DocumentMemory(BaseModel):
    ...
    layer4: Optional[Layer4SemanticNormalization] = None