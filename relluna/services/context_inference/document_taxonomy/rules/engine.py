from __future__ import annotations

from typing import List, Optional

from ..signals import DocumentSignals
from .base import DocumentTypeRule, RuleResult
from .recibo import ReciboRule
from .nota_fiscal import NotaFiscalRule
from .documento_identidade import DocumentoIdentidadeRule


DEFAULT_RULES: List[DocumentTypeRule] = [
    # Ordem não deve ser prioridade; engine escolhe por score.
    NotaFiscalRule(),
    DocumentoIdentidadeRule(),
    ReciboRule(),
]


def infer_document_type(signals: DocumentSignals, rules: Optional[List[DocumentTypeRule]] = None) -> Optional[RuleResult]:
    rules = rules or DEFAULT_RULES

    candidates: List[RuleResult] = []
    for rule in rules:
        res = rule.apply(signals)
        if res is not None:
            candidates.append(res)

    if not candidates:
        return None

    # Escolher maior confiança; em empate, manter o primeiro (ordem estável)
    candidates.sort(key=lambda r: r.confidence, reverse=True)
    return candidates[0]
