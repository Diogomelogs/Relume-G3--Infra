"""
STATUS: legado

Builder simplificado do caminho paralelo `relluna/services/timeline/*`.
Não é a fonte oficial atual da timeline pública.

Fonte oficial:
- `Layer3.eventos_probatorios`
- `relluna/services/read_model/timeline_builder.py`

Mantido apenas para compatibilidade/documentação até a limpeza final.
"""

from typing import List, Dict, Any

LABEL_MAP = {
    "internacao_inicio": "Início da internação",
    "internacao_fim": "Fim da internação",
    "afastamento_inicio": "Início do afastamento",
    "afastamento_fim_estimado": "Fim estimado do afastamento",
    "parecer_emitido": "Emissão de parecer médico",
    "encaminhamento_clinico": "Encaminhamento clínico",
    "registro_condicao_clinica": "Registro de condição clínica",
    "document_issue_date": "Emissão de documento",
}


def _is_obviously_irrelevant_date(event_type: str, date_iso: str | None) -> bool:
    """
    Guarda defensiva extra contra datas muito antigas sendo propagadas
    como emissão de documento (ex: nascimento usando o hint errado).
    """
    if not date_iso:
        return False

    # Regras específicas por tipo
    if event_type in ("birth_date", "document_date_candidate"):
        return True

    if event_type == "document_issue_date":
        # qualquer coisa antes de 1950 é virtualmente impossível como data de emissão
        return date_iso < "1950-01-01"

    return False


def build_timeline(seeds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []

    for s in seeds:
        # 🔥 REGRA 1: só entra se for permitido
        if not s.get("include_in_timeline", False):
            continue

        # 🔥 REGRA 2: precisa ter tipo
        event_type = s.get("event_hint")
        if not event_type:
            continue

        date_iso = s.get("date_iso")

        # 🔥 REGRA 3: bloquear datas irrelevantes (inclui guarda extra)
        if _is_obviously_irrelevant_date(event_type, date_iso):
            continue

        label = LABEL_MAP.get(event_type, event_type)

        event = {
            "event_id": s.get("seed_id"),
            "date": date_iso,
            "event_type": event_type,
            "label": label,
            "evidence_ref": {
                "page": s.get("page"),
                "bbox": s.get("bbox"),
                "snippet": s.get("snippet"),
                "date_literal": s.get("date_literal"),
            },
        }

        events.append(event)

    # ordenação por data + tipo (como fallback de desempate)
    events.sort(key=lambda x: (x["date"], x["event_type"]))

    return events
