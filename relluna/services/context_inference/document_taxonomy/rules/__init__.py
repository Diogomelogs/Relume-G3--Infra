from __future__ import annotations

from typing import Optional, Tuple

from ..signals import DocumentSignals
from ..types import DocumentType
from .engine import DEFAULT_RULES, infer_document_type


def infer_document_type_from_signals(
    signals: DocumentSignals,
) -> Optional[Tuple[DocumentType, float, str]]:
    res = infer_document_type(signals)
    if res is None:
        return None
    return (res.doc_type, res.confidence, res.explanation)


__all__ = [
    "DEFAULT_RULES",
    "infer_document_type",
    "infer_document_type_from_signals",
]
