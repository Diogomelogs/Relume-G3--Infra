from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from relluna.core.document_memory import DocumentMemory
from relluna.services.derivatives.layer5 import apply_layer5
from relluna.services.read_model.timeline_builder import build_document_timeline_read_model


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _artifact_metadata(dm: DocumentMemory) -> Dict[str, Any]:
    artefacts = _get(_get(dm, "layer1"), "artefatos", []) or []
    artefact = artefacts[0] if artefacts else None
    return {
        "uri": _get(artefact, "uri"),
        "name": _get(artefact, "nome"),
        "mimetype": _get(artefact, "mimetype"),
        "size_bytes": _get(artefact, "tamanho_bytes"),
        "hash_sha256": _get(artefact, "hash_sha256"),
        "storage_kind": _get(_get(artefact, "storage_kind"), "value", _get(artefact, "storage_kind")),
        "is_persisted": _get(artefact, "is_persisted"),
    }


def _normalize_citation(citation: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "page": citation.get("page"),
        "snippet": citation.get("snippet"),
        "bbox": citation.get("bbox"),
        "source_path": citation.get("source_path"),
        "confidence": citation.get("confidence"),
        "provenance_status": citation.get("provenance_status"),
        "review_state": citation.get("review_state"),
        "note": citation.get("note"),
    }


def _timeline_for_dossier(timeline_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for event in timeline_data.get("timeline", []) or []:
        provenance_status = event.get("provenance_status") or (event.get("evidence_ref") or {}).get("provenance_status")
        review_state = event.get("review_state") or (event.get("evidence_ref") or {}).get("review_state")
        items.append(
            {
                "event_id": event.get("event_id"),
                "event_type": event.get("event_type"),
                "title": event.get("title") or event.get("label"),
                "description": event.get("description"),
                "date": event.get("date"),
                "confidence": event.get("confidence"),
                "review_state": review_state,
                "provenance_status": provenance_status,
                "artifact_uri": event.get("artifact_uri"),
                "entities": event.get("entities", {}),
                "citations": [_normalize_citation(citation) for citation in (event.get("citations") or [])],
                "evidence_ref": _normalize_citation(event.get("evidence_ref") or {}),
                "assertion_level": (
                    "estimated"
                    if provenance_status == "estimated"
                    else "inferred"
                    if provenance_status in {"inferred", "text_fallback", "snippet_only"}
                    else "observed"
                ),
            }
        )
    return items


def _critical_entities(read_models: Dict[str, Any]) -> Dict[str, Any]:
    entity_summary = read_models.get("entity_summary_v1") or {}
    people = entity_summary.get("people") or {}
    clinical = entity_summary.get("clinical") or {}
    return {
        "patient": people.get("patient"),
        "mother": people.get("mother"),
        "provider": people.get("provider"),
        "cids": clinical.get("cids") or [],
        "crms": clinical.get("crms") or [],
    }


def build_dossier_payload(dm: DocumentMemory) -> Dict[str, Any]:
    if dm.layer5 is None or not _get(dm.layer5, "read_models"):
        dm = apply_layer5(dm)

    timeline_data = build_document_timeline_read_model(dm)
    read_models = _get(dm.layer5, "read_models", {}) or {}
    review_items = read_models.get("review_items_v1") or {}
    dossier_timeline = _timeline_for_dossier(timeline_data)
    warnings = timeline_data.get("warnings") or []

    return {
        "version": "dossier_auditavel_v1",
        "document": {
            "document_id": _get(_get(dm, "layer0"), "documentid"),
            "original_filename": _get(_get(dm, "layer0"), "original_filename"),
            "mimetype": _get(_get(dm, "layer0"), "mimetype"),
            "ingestion_timestamp": (
                _get(_get(dm, "layer0"), "ingestiontimestamp").isoformat()
                if _get(_get(dm, "layer0"), "ingestiontimestamp")
                else None
            ),
            "content_fingerprint": _get(_get(dm, "layer0"), "contentfingerprint"),
            "fingerprint_algorithm": _get(_get(dm, "layer0"), "fingerprint_algorithm"),
            "artifact": _artifact_metadata(dm),
        },
        "timeline": dossier_timeline,
        "entities": _critical_entities(read_models),
        "warnings": warnings,
        "review_items": review_items.get("items") or [],
        "summary": {
            "total_events": len(dossier_timeline),
            "needs_review_count": review_items.get("needs_review_count") or timeline_data.get("summary", {}).get("needs_review_count", 0),
            "anchored_events": timeline_data.get("summary", {}).get("anchored_events", 0),
            "timeline_consistency_score": timeline_data.get("summary", {}).get("timeline_consistency_score"),
            "persistence_state": _get(_get(dm, "layer5"), "persistence_state"),
        },
        "disclaimers": [
            "Derivados de mídia podem continuar não materializados, mas read models Layer5 são persistidos no DocumentMemory e podem ser projetados no read-model store.",
            "Eventos inferidos ou estimados permanecem marcados explicitamente e não equivalem a fato observado.",
        ],
    }


def export_dossier(case_or_dm, output_path: str = "dossier.pdf") -> Dict[str, Any]:
    try:
        from reportlab.pdfgen import canvas
    except ModuleNotFoundError as exc:
        raise RuntimeError("export_dossier requer reportlab instalado para renderização PDF.") from exc

    dossier = build_dossier_payload(case_or_dm) if isinstance(case_or_dm, DocumentMemory) else dict(case_or_dm)
    path = Path(output_path)

    c = canvas.Canvas(str(path))
    y = 800
    c.drawString(40, y, f"Dossie auditavel: {dossier.get('document', {}).get('document_id', '-')}")
    y -= 22
    c.drawString(40, y, f"Fingerprint: {dossier.get('document', {}).get('content_fingerprint', '-')}")
    y -= 22

    for event in dossier.get("timeline", []):
        line = f"{event.get('date', '-')} - {event.get('title', event.get('event_type', 'Evento'))} [{event.get('assertion_level', '-')}]"
        c.drawString(40, y, line[:120])
        y -= 18
        if y < 60:
            c.showPage()
            y = 800

    c.save()

    return {
        "output_path": str(path),
        "dossier": dossier,
    }
