from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.types_basic import ProvenancedString, EvidenceAnchor


@dataclass(frozen=True)
class StructuredContractBlock:
    """
    Estrutura mínima determinística para contrato (MVP):
    - partes (strings brutas)
    - vigência (datas brutas)
    - valores (strings brutas)
    - obrigações (bullets brutos)
    - prazos (strings brutas)

    *Sem IA*, sem “entender” demais. Só coleta indícios com lastro.
    """
    partes: List[str]
    vigencia: Optional[str]
    valores: List[str]
    obrigacoes: List[str]
    prazos: List[str]


def _mk_prov_json(
    key: str,
    payload: Any,
    fonte: str,
    metodo: str,
    anchors: Optional[List[EvidenceAnchor]] = None,
) -> ProvenancedString:
    return ProvenancedString(
        valor=json.dumps(payload, ensure_ascii=False),
        fonte=fonte,
        metodo=metodo,
        estado="confirmado",
        confianca=1.0,
        lastro=anchors or [],
    )


def _find_lines(text: str, patterns: List[str]) -> List[str]:
    out: List[str] = []
    for p in patterns:
        for m in re.finditer(p, text, flags=re.IGNORECASE | re.MULTILINE):
            # pega linha “próxima” do match (simples)
            start = max(0, text.rfind("\n", 0, m.start()) + 1)
            end = text.find("\n", m.end())
            if end == -1:
                end = len(text)
            line = text[start:end].strip()
            if line and line not in out:
                out.append(line)
    return out


def extract_structured_contract_block(dm: DocumentMemory) -> DocumentMemory:
    """
    Preenche layer2.sinais_documentais["structured_contract_v1"] (JSON string)
    SOMENTE se houver texto OCR e indícios fortes de contrato.
    """
    if dm.layer2 is None or dm.layer2.texto_ocr_literal is None:
        return dm

    text = (dm.layer2.texto_ocr_literal.valor or "").strip()
    if not text:
        return dm

    low = text.lower()
    # gate conservador: só ativa se tiver “contrato” e “objeto do contrato” ou “vigência”
    if "contrato" not in low:
        return dm
    if ("objeto do contrato" not in low) and ("vigência" not in low) and ("remuneração" not in low):
        return dm

    # coletas determinísticas
    partes = _find_lines(text, [r"\bcontratante\b", r"\bcontratado\b", r"\bempresa\b", r"\binfluenciador\b"])
    valores = _find_lines(text, [r"r\$\s*\d[\d\.\,]*", r"\bbrl\b\s*\d[\d\.\,]*"])
    vig = _find_lines(text, [r"\bvig[eê]ncia\b.*", r"\bde\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\s+a\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b"])
    obrigacoes = _find_lines(text, [r"\bobrig[aã]ções\b", r"^\s*\d+(\.\d+)?\.\s+.*"])
    prazos = _find_lines(text, [r"\b\d+\s*(dias|dia|horas|hora|meses|m[eê]s)\b", r"\b(at[eé]|até)\s+o\s+dia\s+\d{1,2}\b"])

    block = StructuredContractBlock(
        partes=partes,
        vigencia=vig[0] if vig else None,
        valores=valores,
        obrigacoes=obrigacoes[:50],  # limite defensivo
        prazos=prazos,
    )

    payload: Dict[str, Any] = {
        "kind": "structured_contract_v1",
        "partes": block.partes,
        "vigencia": block.vigencia,
        "valores": block.valores,
        "obrigacoes": block.obrigacoes,
        "prazos": block.prazos,
    }

    dm.layer2.sinais_documentais["structured_contract_v1"] = _mk_prov_json(
        key="structured_contract_v1",
        payload=payload,
        fonte="deterministic_extractors.structured_block",
        metodo="regex_lines_v1",
        anchors=[],
    )
    return dm