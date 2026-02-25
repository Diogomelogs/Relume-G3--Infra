# relluna/services/context_inference/document_taxonomy/apply.py

from __future__ import annotations

from typing import Optional

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.layer3 import Layer3Evidence
from relluna.core.document_memory.types_basic import (
    ConfidenceState,
    EvidenceRef,
    InferredString,
)


_SOURCE = "document_taxonomy.rules"


def _get_ocr_text(dm: DocumentMemory) -> str:
    """
    Retorna texto OCR bruto como string.
    Aceita ProvenancedString, dict ou str.
    """
    if dm.layer2 is None:
        return ""

    o = getattr(dm.layer2, "texto_ocr_literal", None)
    if o is None:
        return ""

    if isinstance(o, str):
        return o
    if isinstance(o, dict):
        return str(o.get("valor") or "")

    return str(getattr(o, "valor", "") or "")


def _infer_document_label_from_text(text: str) -> Optional[tuple[str, float, str, str]]:
    """
    Regras mínimas de taxonomia de documentos baseadas em texto.

    Retorna (label, score, metodo, rule_id) ou None.
    """
    low = text.lower()

    # Exemplo: Nota fiscal via DANFE / keywords
    if "danfe" in low or "nota fiscal" in low:
        return (
            "nota_fiscal",
            0.82,
            "keywords(nota fiscal/danfe)",
            "document_taxonomy.keywords_nota_fiscal_danfe",
        )

    return None


def apply_document_taxonomy(dm: DocumentMemory) -> DocumentMemory:
    """
    Regras determinísticas mínimas de taxonomia de documentos.

    - NÃO altera layer0/layer1/layer2.
    - Cria/preenche layer3.tipo_documento apenas quando houver lastro textual.
    - Registra em layer3.regras_aplicadas quais regras dispararam.
    """
    # Sem layer2 ou sem OCR → não faz nada
    if dm.layer2 is None:
        return dm

    text = _get_ocr_text(dm)
    if not text.strip():
        return dm

    inferred = _infer_document_label_from_text(text)
    if inferred is None:
        return dm

    label, score, metodo, rule_id = inferred

    # Garante existência de layer3
    if dm.layer3 is None:
        dm.layer3 = Layer3Evidence()

    # Lastro aponta para o valor textual usado
    lastro = [EvidenceRef(path="layer2.texto_ocr_literal.valor")]

    dm.layer3.tipo_documento = InferredString(
        valor=label,
        fonte=_SOURCE,
        metodo=metodo,
        estado=ConfidenceState.inferido,
        confianca=score,
        lastro=lastro,
    )

    # Garante lista de regras_aplicadas e registra a regra
    if dm.layer3.regras_aplicadas is None:
        dm.layer3.regras_aplicadas = []
    dm.layer3.regras_aplicadas.append(rule_id)

    return dm
