# layer0.py

from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


class Layer0Custodia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documentid: str
    contentfingerprint: str
    ingestiontimestamp: datetime
    ingestionagent: str

    # Campos exigidos pelos golden e testes
    authenticitystate: Optional[str] = None
    juridicalreadinesslevel: Optional[int] = None

    custodychain: List[Dict[str, Any]] = Field(default_factory=list)
    processingevents: List[Dict[str, Any]] = Field(default_factory=list)
    versiongraph: List[Dict[str, Any]] = Field(default_factory=list)
    integrityproofs: List[Dict[str, Any]] = Field(default_factory=list)