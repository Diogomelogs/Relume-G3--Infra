from __future__ import annotations

from typing import Optional, List

from relluna.core.document_memory import EvidenceRef
from ..types import DocumentType
from ..signals import DocumentSignals
from .base import RuleResult


class NotaFiscalRule:
    name = "nota_fiscal_rule_v1"

    _KEYWORDS_STRONG = (
        "danfe",
        "nota fiscal",
        "nf-e",
        "nfe",
        "chave de acesso",
        "protocolo de autorização",
        "protocolo de autorizacao",
    )

    _KEYWORDS_SUPPORT = (
        "cnpj",
        "inscrição estadual",
        "inscricao estadual",
        "emitente",
        "destinatário",
        "destinatario",
    )

    def match(self, signals: DocumentSignals) -> bool:
        if not signals.ocr_text:
            return False
        low = signals.ocr_text.lower()
        return any(k in low for k in self._KEYWORDS_STRONG) or (
            any(k in low for k in self._KEYWORDS_SUPPORT) and signals.has_currency is True
        )

    def apply(self, signals: DocumentSignals) -> Optional[RuleResult]:
        if not self.match(signals):
            return None

        low = (signals.ocr_text or "").lower()
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

        # score simples: strong => maior
        conf = 0.90 if any(k in low for k in self._KEYWORDS_STRONG) else 0.80
        expl = "OCR contém marcadores típicos de nota fiscal (DANFE/NF-e/chave de acesso)."
        return RuleResult(DocumentType.nota_fiscal, conf, expl, lastro)
