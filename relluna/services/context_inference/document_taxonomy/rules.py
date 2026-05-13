from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .signals import DocumentSignals
from .types import DocumentType
from .rules.engine import infer_document_type


@dataclass(frozen=True)
class RuleResult:
    doc_type: DocumentType
    confidence: float
    lastro: dict
    rule_id: str


def infer_document_type_from_signals(
    signals: DocumentSignals,
) -> Optional[Tuple[DocumentType, float, str]]:
    """
    Shim de compatibilidade para o engine v3.

    Mantém a assinatura antiga e retorna:
    `(doc_type, confidence, explanation)` ou `None`.
    """
    res = infer_document_type(signals)
    if res is None:
        return None
    return (res.doc_type, res.confidence, res.explanation)
