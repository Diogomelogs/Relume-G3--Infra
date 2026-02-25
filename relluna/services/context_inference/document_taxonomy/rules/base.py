from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Optional, List

from relluna.core.document_memory import EvidenceRef
from ..types import DocumentType
from ..signals import DocumentSignals


@dataclass(frozen=True)
class RuleResult:
    doc_type: DocumentType
    confidence: float
    explanation: str
    lastro: List[EvidenceRef]


class DocumentTypeRule(Protocol):
    name: str

    def match(self, signals: DocumentSignals) -> bool: ...

    def apply(self, signals: DocumentSignals) -> Optional[RuleResult]: ...
