from __future__ import annotations

from typing import Optional, Tuple

from .types import DocumentType
from .signals import DocumentSignals
from .rules.engine import infer_document_type

@dataclass
class RuleResult:
    doc_type: DocumentType
    confidence: float
    lastro: dict
    rule_id: str   # <-- adicionar isso

def infer_document_type_from_signals(
    signals: DocumentSignals,
) -> Optional[Tuple[DocumentType, float, str]]:
    """
    Compatibilidade: mantém assinatura antiga.
    Retorna (DocumentType, confiança, explicação) ou None.
    """
    res = infer_document_type(signals)
    if res is None:
        return None
    return (res.doc_type, res.confidence, res.explanation)

return RuleResult(
    doc_type=DocumentType.nota_fiscal,
    confidence=0.95,
    lastro={"regex": "..."},
    rule_id="nota_fiscal_rule"
)
