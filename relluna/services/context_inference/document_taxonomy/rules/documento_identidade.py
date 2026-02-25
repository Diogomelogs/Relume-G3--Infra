from __future__ import annotations

from typing import Optional, List

from relluna.core.document_memory import EvidenceRef
from ..types import DocumentType
from ..signals import DocumentSignals
from .base import RuleResult


class DocumentoIdentidadeRule:
    name = "documento_identidade_rule_v1"

    _KEYWORDS_STRONG = (
        "carteira de identidade",
        "registro geral",
        "identidade",
        "passaporte",
        "carteira nacional de habilitação",
        "cnh",
    )

    _KEYWORDS_SUPPORT = (
        "rg",
        "cpf",
        "data de nascimento",
        "nascimento",
        "naturalidade",
        "filiação",
        "filiacao",
    )

    def match(self, signals: DocumentSignals) -> bool:
        if not signals.ocr_text:
            return False
        low = signals.ocr_text.lower()
        return any(k in low for k in self._KEYWORDS_STRONG) or any(k in low for k in self._KEYWORDS_SUPPORT)

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

        conf = 0.88 if any(k in low for k in self._KEYWORDS_STRONG) else 0.78
        expl = "OCR contém termos típicos de documento de identidade (RG/CPF/identidade/CNH/passaporte)."
        return RuleResult(DocumentType.identidade, conf, expl, lastro)

