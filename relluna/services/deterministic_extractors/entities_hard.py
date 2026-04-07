from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.types_basic import ProvenancedString


_RE_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
_RE_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
_RE_CID = re.compile(r"\b[A-TV-Z]\d{2}(?:\.\d)?\b", re.IGNORECASE)
_RE_CRM = re.compile(r"\bCRM\s*\d{3,8}\s*[A-Z]{0,2}\b", re.IGNORECASE)
_RE_OAB = re.compile(r"\bOAB\s*/?\s*[A-Z]{2}\s*\d{3,8}\b", re.IGNORECASE)
_RE_MONEY = re.compile(r"(?:R\$\s*\d[\d\.\,]*)|\bBRL\s*\d[\d\.\,]*", re.IGNORECASE)
_RE_DATE_DMY = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_RE_CNJ = re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")


def _prov_json(payload: Any, fonte: str, metodo: str) -> ProvenancedString:
    return ProvenancedString(
        valor=json.dumps(payload, ensure_ascii=False),
        fonte=fonte,
        metodo=metodo,
        estado="confirmado",
        confianca=1.0,
        lastro=[],
    )


def _extract_all(regex: re.Pattern, text: str) -> List[str]:
    out: List[str] = []
    for m in regex.finditer(text):
        v = m.group(0).strip()
        if v and v not in out:
            out.append(v)
    return out


def extract_hard_entities(dm: DocumentMemory, max_text_chars: int = 300_000) -> DocumentMemory:
    """
    Determinístico: regex-only (sem IA).
    Persiste em layer2.sinais_documentais["hard_entities_v1"] como JSON string.
    """
    if dm.layer2 is None or dm.layer2.texto_ocr_literal is None:
        return dm

    text = (dm.layer2.texto_ocr_literal.valor or "")
    text = text[:max_text_chars]
    if not text.strip():
        return dm

    payload: List[Dict[str, Any]] = []

    def add(t: str, vals: List[str]) -> None:
        for v in vals:
            payload.append({"type": t, "value": v})

    add("cnpj", _extract_all(_RE_CNPJ, text))
    add("cpf", _extract_all(_RE_CPF, text))
    add("cnj", _extract_all(_RE_CNJ, text))
    add("cid", _extract_all(_RE_CID, text))
    add("crm", _extract_all(_RE_CRM, text))
    add("oab", _extract_all(_RE_OAB, text))
    add("valor_monetario", _extract_all(_RE_MONEY, text))
    add("data_textual", _extract_all(_RE_DATE_DMY, text))

    if not payload:
        return dm

    dm.layer2.sinais_documentais["hard_entities_v1"] = _prov_json(
        payload,
        fonte="deterministic_extractors.entities_hard",
        metodo="regex_v1",
    )
    return dm