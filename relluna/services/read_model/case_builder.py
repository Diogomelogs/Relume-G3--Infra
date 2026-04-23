from __future__ import annotations

from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from relluna.core.document_memory import DocumentMemory
from relluna.services.derivatives.layer5 import apply_layer5
from relluna.services.legal.case_engine import build_case_outputs
from relluna.services.read_model.projector import project_dm_to_read_model
from relluna.services.read_model.timeline_builder import build_document_timeline_read_model

CASE_SCHEMA = "relluna.read_model.case.document.v1"


def _artifact_uri(dm: DocumentMemory) -> Optional[str]:
    artefacts = getattr(dm.layer1, "artefatos", None) or []
    if not artefacts:
        return None
    original = next((item for item in artefacts if getattr(item, "tipo", None) == "original"), None)
    return getattr((original or artefacts[0]), "uri", None)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _dedup_source_signals(*groups: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for group in groups:
        for item in group:
            if not item or item in seen:
                continue
            seen.add(item)
            out.append(item)
    return out


def _legal_section(dm: DocumentMemory) -> Dict[str, Any]:
    outputs = build_case_outputs([dm])
    extraction = None
    for item in outputs.get("canonical_extractions") or []:
        if isinstance(item, dict):
            extraction = item
            break

    timeline_facts = [item for item in (outputs.get("timeline_facts") or []) if isinstance(item, dict)]
    alerts = [item for item in (outputs.get("legal_alerts") or []) if isinstance(item, dict)]

    return {
        "canonical_fields": extraction,
        "timeline_facts": timeline_facts,
        "alerts": alerts,
        "summary": {
            "total_canonical_fields": len((extraction or {}).get("fields") or []),
            "total_timeline_facts": len(timeline_facts),
            "total_alerts": len(alerts),
            "warnings": list((extraction or {}).get("warnings") or []),
        },
    }


def build_document_case_read_model(dm: DocumentMemory) -> Dict[str, Any]:
    if dm.layer5 is None or not getattr(dm.layer5, "read_models", None):
        dm = apply_layer5(dm)

    projected = project_dm_to_read_model(dm)
    timeline_public = build_document_timeline_read_model(dm)
    layer5_read_models = getattr(dm.layer5, "read_models", None) or {}
    entity_summary = layer5_read_models.get("entity_summary_v1") or {}
    review_items = layer5_read_models.get("review_items_v1") or {}
    legal = _legal_section(dm)

    timeline_summary = timeline_public.get("summary") or {}
    legal_summary = legal.get("summary") or {}
    timeline_warnings = [item for item in (timeline_public.get("warnings") or []) if isinstance(item, dict)]
    review_list = [item for item in (review_items.get("items") or []) if isinstance(item, dict)]
    legal_alerts = [item for item in (legal.get("alerts") or []) if isinstance(item, dict)]

    return {
        "schema": CASE_SCHEMA,
        "document": {
            "document_id": projected.document_id,
            "title": projected.title,
            "summary": projected.summary,
            "doc_type": projected.doc_type,
            "media_type": projected.media_type,
            "artifact_uri": _artifact_uri(dm),
            "date_canonical": projected.date_canonical,
            "period_label": projected.period_label,
            "tags": list(projected.tags or []),
            "created_at": projected.created_at.isoformat() if getattr(projected, "created_at", None) else _now_iso(),
        },
        "summary": {
            "total_timeline_events": int(timeline_summary.get("total_events") or 0),
            "anchored_events": int(timeline_summary.get("anchored_events") or 0),
            "needs_review_count": int(timeline_summary.get("needs_review_count") or review_items.get("needs_review_count") or 0),
            "timeline_consistency_score": timeline_summary.get("timeline_consistency_score"),
            "total_review_items": int(review_items.get("total_items") or len(review_list)),
            "total_legal_alerts": len(legal_alerts),
            "total_legal_timeline_facts": int(legal_summary.get("total_timeline_facts") or 0),
            "warnings": timeline_warnings,
        },
        "entities": entity_summary,
        "timeline": timeline_public,
        "review": review_items,
        "legal": legal,
        "provenance": {
            "source_signals": _dedup_source_signals(
                ["entities_canonical_v1", "legal_canonical_fields_v1", "timeline_seed_v2"],
                ["layer3.eventos_probatorios" if getattr(dm.layer3, "eventos_probatorios", None) else ""],
                ["layer5.read_models.entity_summary_v1", "layer5.read_models.review_items_v1"],
            ),
            "compatibility_notes": [
                "timeline pública continua vindo de /documents/{documentid}/timeline",
                "legal_canonical_fields_v1 é projeção compatível de entities_canonical_v1",
                "entity_summary_v1 e review_items_v1 seguem como read models derivados de Layer5",
            ],
        },
    }
