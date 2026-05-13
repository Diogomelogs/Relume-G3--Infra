from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

# Layers
from .layer0 import Layer0Custodia
from .layer1 import Layer1, ArtefatoBruto, MediaType, OriginType
from .layer2 import Layer2Evidence
from .layer3 import Layer3Evidence
from .layer3 import SemanticEntity
from .layer4_canonical import Layer4SemanticNormalization
from relluna.core.contracts.document_memory_contract import Layer5Derivatives
from .layer6 import Layer6Optimization
from relluna.core.document_memory.types_basic import TemporalReference


# Basic types
from .types_basic import (
    ProvenancedString,
    ProvenancedNumber,
    ProvenancedDatetime,
    ProvenancedDate,
    InferredString,
    InferredDatetime,
    EvidenceNumber,
    ConfidenceState,
    EvidenceRef,
    SemanticEntity,
    InferenceMeta,
    GpsExif,
    QualidadeSinal,
    EntidadeVisualObjetiva,
)

# Aliases de compatibilidade (somente após imports)
Layer0 = Layer0Custodia
Layer1Artefatos = Layer1
Layer2EvidenceBaseModel = Layer2Evidence
Layer3EvidenceBaseModel = Layer3Evidence
Layer4 = Layer4SemanticNormalization
Layer5 = Layer5Derivatives
Layer6 = Layer6Optimization


class DocumentMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "v0.1.0"

    layer0: Layer0Custodia
    layer1: Optional[Layer1Artefatos] = None
    layer2: Optional[Layer2Evidence] = None
    layer3: Optional[Layer3Evidence] = None
    layer4: Optional[Layer4SemanticNormalization] = None
    layer5: Optional[Layer5Derivatives] = None
    layer6: Optional[Layer6Optimization] = None


from .models_v0_2_0 import DocumentMemoryCanonical, DocumentMemory_v0_2_0


__all__ = [
    "DocumentMemory",
    "DocumentMemoryCanonical",
    "DocumentMemory_v0_2_0",
    # Layers
    "Layer0",
    "Layer1",
    "Layer2Evidence",
    "Layer3Evidence",
    "Layer4SemanticNormalization",
    "Layer5Derivatives",
    "Layer6Optimization",
    # Aliases
    "Layer2EvidenceBaseModel",
    "Layer3EvidenceBaseModel",
    # Models
    "Layer0Custodia",
    "Layer1Artefatos",
    "ArtefatoBruto",
    # Enums
    "MediaType",
    "OriginType",
    # Basic types
    "ProvenancedString",
    "ProvenancedNumber",
    "ProvenancedDatetime",
    "ProvenancedDate",
    "InferredString",
    "InferredDatetime",
    "EvidenceNumber",
    "ConfidenceState",
    "EvidenceRef",
    "InferenceMeta",
    "GpsExif",
    "QualidadeSinal",
    "EntidadeVisualObjetiva",
]

# Garante que todas as referências de tipo (incluindo InferredString) são resolvidas
DocumentMemory.model_rebuild()
Layer3Evidence.model_rebuild()
