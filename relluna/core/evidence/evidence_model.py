from pydantic import BaseModel
from typing import List, Optional

class EvidenceRef(BaseModel):
    document_id: str
    page: int
    bbox: List[float]
    snippet: str


class Evidence(BaseModel):
    evidence_id: str
    evidence_type: str
    value: str
    refs: List[EvidenceRef]


class TimelineEvent(BaseModel):
    event_id: str
    date: str
    label: str
    evidences: List[str]