# layer0.py

from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

import hashlib

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

CHUNK_SIZE = 8192


def compute_contentfingerprint_from_file(path: Union[str, Path]) -> str:
    """
    Calcula o SHA-256 completo de um arquivo em disco e devolve em hex (64 caracteres).
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
    Calcula o SHA-256 completo de um buffer em memória.
    Útil caso você já tenha os bytes do upload.
    """
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()
