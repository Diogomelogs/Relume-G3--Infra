from __future__ import annotations
"""
STATUS: wrapper compatível legado

Este módulo não é a fonte oficial da timeline pública.
Hoje a superfície oficial converge para:
- `Layer3.eventos_probatorios`
- `relluna/services/read_model/timeline_builder.py`

Mantemos este builder apenas como compatibilidade do caminho paralelo
`relluna/services/timeline/*`.
"""

import hashlib
from typing import Any, Dict, List

EVENT_TITLE_MAP = {
    "internacao_inicio": "Início da internação",
    "internacao_fim": "Fim da internação",
    "attendance_date": "Atendimento registrado",
    "document_issue_date": "Emissão do documento",
    "afastamento_inicio": "Início do afastamento",
    "afastamento_fim_estimado": "Fim estimado do afastamento",
    "birth_date": "Data de nascimento",
}

EVENT_DESCRIPTION_MAP = {
    "internacao_inicio": "Registro de início de internação identificado no documento.",
    "internacao_fim": "Registro de fim de internação identificado no documento.",
    "attendance_date": "Data de atendimento clínico registrada no documento.",
    "document_issue_date": "Data de emissão do documento clínico.",
    "afastamento_inicio": "Documento recomenda afastamento a partir desta data.",
    "afastamento_fim_estimado": "Data estimada de término do afastamento com base na duração detectada.",
    "birth_date": "Data de nascimento do paciente identificada no documento.",
}

def _build_entity_summary(entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {
        "patient": None,
        "mother": None,
        "provider": None,
        "cids": [],
        "crms": [],
        "duration_days": None,
    }
    for item in entities:
        t = item.get("type")
        if t == "patient_name" and not summary["patient"]:
            summary["patient"] = item.get("value")
        elif t == "mother_name" and not summary["mother"]:
            summary["mother"] = item.get("value")
        elif t == "provider_name" and not summary["provider"]:
            summary["provider"] = item.get("value")
        elif t == "cid" and item.get("value") not in summary["cids"]:
            summary["cids"].append(item.get("value"))
        elif t == "crm" and item.get("value") not in summary["crms"]:
            summary["crms"].append(item.get("value"))
        elif t == "duration_days" and summary["duration_days"] is None:
            summary["duration_days"] = item.get("value_int")
    return summary

def build_events_v2(
    timeline_seeds: List[Dict[str, Any]],
    document_type: str,
    entities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    entity_summary = _build_entity_summary(entities)

    for seed in timeline_seeds:
        if not seed.get("include_in_timeline", False):
            continue

        event_hint = seed["event_hint"]
        base = f"{seed['date_iso']}_{event_hint}_{document_type}"
        event_id = hashlib.sha256(base.encode()).hexdigest()[:16]

        citation = {
            "page": seed.get("page"),
            "bbox": seed.get("bbox"),
            "snippet": seed.get("snippet"),
            "source_path": seed.get("source_path"),
        }

        events.append({
            "event_id": event_id,
            "date_iso": seed["date_iso"],
            "date": seed["date_iso"],
            "event_type": event_hint,
            "document_type": document_type,
            "title": EVENT_TITLE_MAP.get(event_hint, "Evento detectado"),
            "description": EVENT_DESCRIPTION_MAP.get(event_hint, "Evento temporal detectado no documento."),
            "confidence": seed.get("confidence", 0.84),
            "review_state": seed.get("review_state", "review_recommended"),
            "provenance_status": seed.get("provenance_status", "missing"),
            "evidence": {
                "page": seed.get("page"),
                "bbox": seed.get("bbox"),
                "snippet": seed.get("snippet"),
            },
            "citations": [citation],
            "entities": entity_summary,
        })

    events.sort(key=lambda x: (x["date_iso"], x["event_type"], x["event_id"]))
    return events


def build_events(
    timeline_seeds: List[Dict[str, Any]],
    document_type: str,
    entities: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """
    Wrapper compatível para o caminho legado `timeline_pipeline.py`.
    """
    return build_events_v2(
        timeline_seeds=timeline_seeds,
        document_type=document_type,
        entities=entities or [],
    )
