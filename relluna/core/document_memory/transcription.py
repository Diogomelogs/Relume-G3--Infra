from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field


class TranscriptionSegment(BaseModel):
    """
    Segmento temporal da transcrição.
    speaker é opcional (diarização pode ser ligada depois).
    """
    start: float = Field(..., ge=0.0)
    end: float = Field(..., ge=0.0)
    text: str = Field(..., min_length=1)
    speaker: Optional[str] = None