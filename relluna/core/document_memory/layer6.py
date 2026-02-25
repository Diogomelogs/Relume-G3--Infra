from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

class Layer6Optimization(BaseModel):
    model_config = ConfigDict(extra="allow")
    embeddings: Optional[List[float]] = None
    index_refs: List[str] = Field(default_factory=list)
    extra: Dict[str, Any] = Field(default_factory=dict)
