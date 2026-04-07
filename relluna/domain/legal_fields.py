from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class EvidenceAnchor(BaseModel):
    page: Optional[int] = None
    bbox: Optional[list[float]] = None
    snippet: Optional[str] = None


class CanonicalField(BaseModel):
    name: str
    value: Any = None
    normalized_value: Any = None
    confidence: float = 0.0
    source_doc_type: Optional[str] = None
    anchor: Optional[EvidenceAnchor] = None


class CanonicalExtraction(BaseModel):
    document_id: str
    doc_type: str
    confidence: float = 0.0
    fields: List[CanonicalField] = []


class TimelineFact(BaseModel):
    fact_type: str
    date_iso: str
    value: Any = None
    document_id: Optional[str] = None
    doc_type: Optional[str] = None
    anchor: Optional[EvidenceAnchor] = None
    metadata: Dict[str, Any] = {}


class LegalAlert(BaseModel):
    code: str
    title: str
    severity: str
    message: str
    supporting_facts: List[Dict[str, Any]] = []