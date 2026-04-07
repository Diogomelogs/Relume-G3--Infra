from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from relluna.core.document_memory import DocumentMemory


def _load_signal_json(dm: DocumentMemory, key: str) -> Optional[Any]:
    if dm.layer2 is None:
        return None
    s = dm.layer2.sinais_documentais.get(key)
    if not s or not getattr(s, "valor", None):
        return None
    try:
        return json.loads(s.valor)
    except Exception:
        return None


def _normalize_timeline_items(raw_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        date_iso = item.get("date_iso") or item.get("date")
        if not date_iso:
            continue

        event_id = item.get("seed_id") or item.get("event_id")
        event_type = item.get("event_type") or "evento_detectado"

        evidence = {
            "page": item.get("page"),
            "bbox": item.get("bbox"),
            "snippet": item.get("snippet"),
            "date_literal": item.get("date_literal"),
        }

        normalized.append(
            {
                "event_id": event_id,
                "date": date_iso,
                "label": event_type,
                "event_type": event_type,
                "evidence_ref": evidence,
            }
        )

    normalized.sort(key=lambda x: (x["date"], x["event_id"] or ""))
    return normalized


def build_document_timeline_read_model(dm: DocumentMemory) -> Dict[str, Any]:
    """
    Read model por documento.
    Prioridade:
    1. timeline_seed_v2
    2. timeline_seed_v1
    """
    l0 = dm.layer0
    l1 = dm.layer1

    timeline_v2 = _load_signal_json(dm, "timeline_seed_v2") or []
    timeline_v1 = _load_signal_json(dm, "timeline_seed_v1") or []
    hard_entities = (
        _load_signal_json(dm, "hard_entities_v2")
        or _load_signal_json(dm, "hard_entities_v1")
        or []
    )

    timeline_raw = timeline_v2 if timeline_v2 else timeline_v1
    timeline = _normalize_timeline_items(timeline_raw)

    anchored_events = sum(
        1
        for ev in timeline
        if ev.get("evidence_ref", {}).get("page") is not None
        and ev.get("evidence_ref", {}).get("bbox") is not None
    )

    return {
        "schema": "relluna.read_model.timeline.document.v2",
        "document": {
            "documentid": getattr(l0, "documentid", None),
            "contentfingerprint": getattr(l0, "contentfingerprint", None),
            "fingerprint_algorithm": getattr(l0, "fingerprint_algorithm", None),
            "ingestiontimestamp": (
                getattr(l0, "ingestiontimestamp", None).isoformat()
                if getattr(l0, "ingestiontimestamp", None)
                else None
            ),
            "original_filename": getattr(l0, "original_filename", None),
            "mimetype": getattr(l0, "mimetype", None),
            "size_bytes": getattr(l0, "size_bytes", None),
            "midia": getattr(l1, "midia", None).value if getattr(l1, "midia", None) else None,
            "origem": getattr(l1, "origem", None).value if getattr(l1, "origem", None) else None,
        },
        "summary": {
            "total_events": len(timeline),
            "anchored_events": anchored_events,
            "hard_entities_count": len(hard_entities),
        },
        "timeline": timeline,
        "hard_entities": hard_entities,
    }