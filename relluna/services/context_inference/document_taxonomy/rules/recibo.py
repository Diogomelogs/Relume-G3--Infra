from __future__ import annotations

from typing import Optional, List

from relluna.core.document_memory import EvidenceRef
from ..types import DocumentType
from ..signals import DocumentSignals
from .base import RuleResult


class ReciboRule:
    name = "recibo_rule_v1"

    _KEYWORDS = (
        "recibo",
        "comprovante",
        "bilhete eletr",
        "pagamento",
        "transação",
        "transacao",
    )

    def match(self, signals: DocumentSignals) -> bool:
        if not signals.ocr_text:
            return False
        low = signals.ocr_text.lower()
        return any(k in low for k in self._KEYWORDS)

    def apply(self, signals: DocumentSignals) -> Optional[RuleResult]:
        if not self.match(signals):
            return None

        lastro: List[EvidenceRef] = []
        if signals.ocr_text:
            lastro.append(
                EvidenceRef(
                    layer=2,
                    path="layer2.texto_ocr_literal.valor",
                    tipo="ocr",
                    valor_resumo=signals.ocr_text[:80],
                )
            )

        # Confiança determinística (MVP)
        conf = 0.82
        expl = "OCR contém termos típicos de recibo/comprovante."
        return RuleResult(DocumentType.recibo, conf, expl, lastro)
