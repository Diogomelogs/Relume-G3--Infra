from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from relluna.core.document_memory import DocumentMemory, MediaType
from relluna.core.contracts.document_memory_contract import (
    Layer5Derivatives,
    Derivado,
)
from relluna.services.entities.document_date_resolver import DocumentDateResolver
from relluna.services.entities.people_resolver import PeopleResolver
from relluna.services.evidence.signals import load_critical_signal_json
from relluna.services.read_model.timeline_builder import (
    build_document_timeline_read_model,
    build_timeline_consistency_warning,
)

_BUILDER_VERSION = "layer5_read_model_v3"
_PLACEHOLDER_PERSISTENCE_STATE = "placeholder_not_persisted"
_PEOPLE_RESOLVER = PeopleResolver()
_DOCUMENT_DATE_RESOLVER = DocumentDateResolver()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _review_state(confidence: Optional[float]) -> str:
    c = confidence or 0.0
    if c >= 0.95:
        return "auto_confirmed"
    if c >= 0.80:
        return "review_recommended"
    return "needs_review"


def _load_signal_json(dm: DocumentMemory, key: str) -> Any:
    if key in {"page_evidence_v1", "entities_canonical_v1", "timeline_seed_v2"}:
        return load_critical_signal_json(dm, key)
    if dm.layer2 is None:
        return None
    sig = dm.layer2.sinais_documentais.get(key)
    if not sig or not getattr(sig, "valor", None):
        return None
    try:
        return json.loads(sig.valor)
    except Exception:
        return None


def _load_entities_canonical(dm: DocumentMemory) -> Dict[str, Any]:
    data = _load_signal_json(dm, "entities_canonical_v1")
    if isinstance(data, dict):
        return data
    return {}


def _canonical_document_type(dm: DocumentMemory) -> Optional[str]:
    canonical = _load_entities_canonical(dm)
    document_type = canonical.get("document_type")
    if document_type:
        return document_type

    if dm.layer3 and dm.layer3.tipo_documento:
        return getattr(dm.layer3.tipo_documento, "valor", None)

    return None


def _load_page_evidence(dm: DocumentMemory) -> List[Dict[str, Any]]:
    data = _load_signal_json(dm, "page_evidence_v1")
    return data if isinstance(data, list) else []


def _load_layout_spans(dm: DocumentMemory) -> List[Dict[str, Any]]:
    data = _load_signal_json(dm, "layout_spans_v1")
    return data if isinstance(data, list) else []


def _canonical_semantic_resolution(dm: DocumentMemory, canonical: Dict[str, Any]) -> Dict[str, Any]:
    semantic = canonical.get("semantic_resolution_v1")
    if isinstance(semantic, dict):
        return semantic

    page_evidence = _load_page_evidence(dm)
    layout_spans = _load_layout_spans(dm)
    return {
        "people": _PEOPLE_RESOLVER.resolve(page_evidence, layout_spans, canonical),
        "document_date": _DOCUMENT_DATE_RESOLVER.resolve(page_evidence, layout_spans, canonical),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Read model: timeline_v1
# ─────────────────────────────────────────────────────────────────────────────

def _citation_to_dict(c: Any, document_id: Optional[str]) -> dict:
    return {
        "document_id": document_id,
        "source_path": getattr(c, "source_path", None),
        "page": getattr(c, "page", None),
        "bbox": getattr(c, "bbox", None),
        "snippet": getattr(c, "snippet", None),
        "confidence": getattr(c, "confidence", None),
        "provenance_status": getattr(c, "provenance_status", None),
        "review_state": getattr(c, "review_state", None),
        "note": getattr(c, "note", None),
    }


def _fallback_title(event_type: Optional[str]) -> str:
    if not event_type:
        return "Evento probatório"

    label_map = {
        "internacao_inicio": "Início da internação",
        "internacao_fim": "Fim da internação",
        "afastamento_inicio": "Início do afastamento",
        "afastamento_fim_estimado": "Fim estimado do afastamento",
        "document_issue_date": "Data de emissão",
        "parecer_emitido": "Emissão de parecer médico",
        "encaminhamento_clinico": "Encaminhamento clínico",
        "registro_condicao_clinica": "Registro de condição clínica",
    }
    return label_map.get(event_type, str(event_type).replace("_", " ").capitalize())


def _event_sort_key(event_dict: Dict[str, Any]) -> tuple:
    event_type = event_dict.get("event_type") or ""
    priority_map = {
        "internacao_inicio": 10,
        "internacao_fim": 20,
        "document_issue_date": 40,
        "parecer_emitido": 45,
        "encaminhamento_clinico": 50,
        "registro_condicao_clinica": 55,
        "afastamento_inicio": 60,
        "afastamento_fim_estimado": 70,
    }
    return (
        event_dict.get("date_iso") or "9999-99-99",
        priority_map.get(event_type, 500),
        event_dict.get("event_id") or "",
    )


def _normalize_event_entities(
    entities: Dict[str, Any],
    canonical: Dict[str, Any],
) -> Dict[str, Any]:
    patient = entities.get("patient")
    mother = entities.get("mother")
    provider = entities.get("provider")
    cids = list(entities.get("cids") or [])
    crms = list(entities.get("crms") or [])

    if not patient:
        patient = ((canonical.get("patient") or {}).get("name"))
    if not provider:
        provider = ((canonical.get("provider") or {}).get("name"))
    if not cids:
        cids = [
            item.get("code")
            for item in ((canonical.get("clinical") or {}).get("cids") or [])
            if isinstance(item, dict) and item.get("code")
        ]
    if not crms:
        display = _crm_display((canonical.get("provider") or {}).get("crm"))
        if display:
            crms = [display]

    return {
        "patient": patient,
        "mother": mother,
        "provider": provider,
        "cids": list(dict.fromkeys([c for c in cids if c])),
        "crms": list(dict.fromkeys([c for c in crms if c])),
    }


def _build_timeline_v1(dm: DocumentMemory) -> dict:
    document_id = dm.layer0.documentid if dm.layer0 else None
    document_type = _canonical_document_type(dm)
    canonical = _load_entities_canonical(dm)

    events_out: List[dict] = []

    for event in getattr(dm.layer3, "eventos_probatorios", None) or []:
        event_type = getattr(event, "event_type", None)
        if not event_type:
            tipo_ev = getattr(event, "tipo_evento", None)
            event_type = getattr(tipo_ev, "valor", None) if tipo_ev else None

        if not event_type:
            continue

        confidence = getattr(event, "confidence", None)
        if confidence is None:
            confidence = getattr(event, "confianca", None)

        entities_raw: Dict[str, Any] = getattr(event, "entities", None) or {}
        entities = _normalize_event_entities(entities_raw, canonical)

        citations_raw = getattr(event, "citations", None) or []
        if not citations_raw:
            citations_raw = getattr(event, "evidencias_origem", None) or []

        citations_out = [_citation_to_dict(c, document_id) for c in citations_raw]

        cids = entities.get("cids") or []
        tags = list(dict.fromkeys([f"cid:{cid}" for cid in cids if cid]))

        title = getattr(event, "title", None) or _fallback_title(event_type)
        description = getattr(event, "description", None) or getattr(event, "descricao_curta", None)

        events_out.append(
            {
                "event_id": getattr(event, "event_id", None),
                "event_type": event_type,
                "title": title,
                "description": description,
                "date_iso": getattr(event, "date_iso", None),
                "confidence": confidence,
                "review_state": getattr(event, "review_state", None) or _review_state(confidence),
                "provenance_status": getattr(event, "provenance_status", None),
                "derivation_rule": getattr(event, "derivation_rule", None),
                "tags": tags,
                "entities": entities,
                "citations": citations_out,
            }
        )

    if not events_out:
        public_timeline = build_document_timeline_read_model(dm)
        for event in public_timeline.get("timeline", []) or []:
            if not isinstance(event, dict):
                continue

            citations = [
                {
                    "document_id": document_id,
                    "source_path": citation.get("source_path"),
                    "page": citation.get("page"),
                    "bbox": citation.get("bbox"),
                    "snippet": citation.get("snippet"),
                    "confidence": citation.get("confidence"),
                    "provenance_status": citation.get("provenance_status"),
                    "review_state": citation.get("review_state"),
                    "note": citation.get("note"),
                }
                for citation in (event.get("citations") or [])
                if isinstance(citation, dict)
            ]

            events_out.append(
                {
                    "event_id": event.get("event_id"),
                    "event_type": event.get("event_type"),
                    "title": event.get("title") or _fallback_title(event.get("event_type")),
                    "description": event.get("description"),
                    "date_iso": event.get("date"),
                    "confidence": event.get("confidence"),
                    "review_state": event.get("review_state") or _review_state(event.get("confidence")),
                    "provenance_status": event.get("provenance_status"),
                    "derivation_rule": "timeline_public_fallback_v1",
                    "tags": list(
                        dict.fromkeys(
                            [f"cid:{cid}" for cid in (event.get("entities", {}) or {}).get("cids", []) if cid]
                        )
                    ),
                    "entities": event.get("entities", {}) or {},
                    "citations": citations,
                }
            )

    events_out.sort(key=_event_sort_key)
    consistency_warning = build_timeline_consistency_warning(dm)

    return {
        "version": _BUILDER_VERSION,
        "document_id": document_id,
        "document_type": document_type,
        "generated_at": _now_iso(),
        "total_events": len(events_out),
        "timeline_consistency_score": 0.0 if consistency_warning else 100.0,
        "warnings": [consistency_warning] if consistency_warning else [],
        "needs_review_count": sum(
            1 for e in events_out
            if e.get("review_state") in ("needs_review", "review_recommended")
        ),
        "events": events_out,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Read model: entity_summary_v1
# ─────────────────────────────────────────────────────────────────────────────

def _collect_from_canonical(canonical: Dict[str, Any]) -> Dict[str, Any]:
    patient = ((canonical.get("patient") or {}).get("name"))
    provider = ((canonical.get("provider") or {}).get("name"))
    mother = ((canonical.get("mother") or {}).get("name"))

    clinical = canonical.get("clinical") or {}
    cids = [
        item.get("code")
        for item in (clinical.get("cids") or [])
        if isinstance(item, dict) and item.get("code")
    ]

    display = _crm_display((canonical.get("provider") or {}).get("crm"))
    crms = [display] if display else []

    return {
        "patient": patient,
        "mother": mother,
        "provider": provider,
        "cids": cids,
        "crms": crms,
    }


def _crm_display(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        display = value.get("display")
        if display:
            return str(display)
        number = value.get("number")
        uf = value.get("uf")
        if number:
            return f"CRM {number} {uf}".strip() if uf else f"CRM {number}"
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _build_entity_summary_v1(dm: DocumentMemory) -> dict:
    document_id = dm.layer0.documentid if dm.layer0 else None
    canonical = _load_entities_canonical(dm)
    canonical_data = _collect_from_canonical(canonical)

    all_cids: List[str] = list(canonical_data["cids"])
    all_crms: List[str] = list(canonical_data["crms"])
    all_cpfs: List[str] = []
    all_cnpjs: List[str] = []

    patient = canonical_data["patient"]
    provider = canonical_data["provider"]
    mother = canonical_data["mother"]

    page_evidence = _load_signal_json(dm, "page_evidence_v1") or []
    if isinstance(page_evidence, list):
        for item in page_evidence:
            people = item.get("people") or {}
            patient = patient or people.get("patient_name")
            provider = provider or people.get("provider_name")
            mother = mother or people.get("mother_name")

    hard = _load_signal_json(dm, "hard_entities_v2") or []
    if isinstance(hard, list):
        for item in hard:
            t = item.get("type")
            if t == "cid" and item.get("value"):
                all_cids.append(item["value"])
            elif t == "crm" and item.get("value"):
                uf = item.get("uf") or ""
                all_crms.append(f"CRM {item['value']} {uf}".strip())
            elif t == "cpf" and item.get("value"):
                all_cpfs.append(item["value"])
            elif t == "cnpj" and item.get("value"):
                all_cnpjs.append(item["value"])

    for event in getattr(dm.layer3, "eventos_probatorios", None) or []:
        entities = getattr(event, "entities", None) or {}
        patient = patient or entities.get("patient")
        provider = provider or entities.get("provider")
        mother = mother or entities.get("mother")
        all_cids.extend(entities.get("cids") or [])
        all_crms.extend(entities.get("crms") or [])
        all_cpfs.extend(entities.get("cpfs") or [])
        all_cnpjs.extend(entities.get("cnpjs") or [])

    return {
        "version": "entity_summary_v1",
        "document_id": document_id,
        "document_type": _canonical_document_type(dm),
        "generated_at": _now_iso(),
        "people": {
            "patient": patient,
            "mother": mother,
            "provider": provider,
        },
        "clinical": {
            "cids": list(dict.fromkeys([x for x in all_cids if x])),
            "crms": list(dict.fromkeys([x for x in all_crms if x])),
        },
        "administrative": {
            "cpfs": list(dict.fromkeys([x for x in all_cpfs if x])),
            "cnpjs": list(dict.fromkeys([x for x in all_cnpjs if x])),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Read model: review_items_v1
# ─────────────────────────────────────────────────────────────────────────────

def _artifact_uri(dm: DocumentMemory) -> Optional[str]:
    artefatos = getattr(dm.layer1, "artefatos", None) or []
    if not artefatos:
        return None
    original = next((item for item in artefatos if getattr(item, "tipo", None) == "original"), None)
    return getattr((original or artefatos[0]), "uri", None)


def _normalize_evidence_ref_dict(ref: Any) -> Dict[str, Any]:
    return {
        "page": _get(ref, "page"),
        "bbox": _get(ref, "bbox"),
        "snippet": _get(ref, "snippet"),
        "source_path": _get(ref, "source_path"),
        "confidence": _get(ref, "confidence"),
        "provenance_status": _get(ref, "provenance_status"),
        "review_state": _get(ref, "review_state"),
        "date_literal": _get(ref, "date_literal"),
        "note": _get(ref, "note"),
    }


def _normalize_evidence_refs(refs: Any) -> List[Dict[str, Any]]:
    return [_normalize_evidence_ref_dict(ref) for ref in (refs or [])]


def _suggested_action(review_state: Optional[str], provenance_status: Optional[str], has_bbox: bool) -> str:
    if provenance_status == "estimated":
        return "confirm_or_recalculate_estimated_event"
    if provenance_status in {"inferred", "text_fallback", "snippet_only"} or not has_bbox:
        return "confirm_with_document_evidence"
    if review_state in {"needs_review", "review_recommended"}:
        return "review_and_confirm"
    return "monitor"


def _make_review_item(
    *,
    item_type: str,
    field: str,
    value: Any,
    confidence: Optional[float],
    review_state: Optional[str],
    provenance_status: Optional[str],
    reason: str,
    evidence_refs: List[Dict[str, Any]],
    source_signal: str,
    suggested_action: Optional[str] = None,
) -> Dict[str, Any]:
    has_bbox = any(ref.get("bbox") for ref in evidence_refs)
    return {
        "item_type": item_type,
        "field": field,
        "value": value,
        "confidence": confidence,
        "review_state": review_state or _review_state(confidence),
        "provenance_status": provenance_status or ("exact" if has_bbox else "inferred"),
        "reason": reason,
        "evidence_refs": evidence_refs,
        "source_signal": source_signal,
        "suggested_action": suggested_action
        or _suggested_action(review_state, provenance_status, has_bbox),
    }


def _build_people_review_items(dm: DocumentMemory, canonical: Dict[str, Any]) -> List[Dict[str, Any]]:
    semantic = _canonical_semantic_resolution(dm, canonical)
    people = semantic.get("people") or {}
    items: List[Dict[str, Any]] = []
    for role in ("patient", "mother", "provider"):
        resolution = people.get(role) or {}
        value = resolution.get("name") or ((canonical.get(role) or {}).get("name"))
        if not value:
            continue
        evidence_refs = _normalize_evidence_refs(resolution.get("evidence_refs") or (canonical.get(role) or {}).get("evidence_refs") or [])
        if not evidence_refs and (canonical.get(role) or {}).get("evidence"):
            evidence_refs = [_normalize_evidence_ref_dict((canonical.get(role) or {}).get("evidence"))]
        provenance_status = (
            (evidence_refs[0].get("provenance_status") if evidence_refs else None)
            or ((canonical.get(role) or {}).get("evidence") or {}).get("provenance_status")
        )
        items.append(
            _make_review_item(
                item_type="person",
                field=role,
                value=value,
                confidence=resolution.get("confidence") or (canonical.get(role) or {}).get("confidence"),
                review_state=resolution.get("review_state") or (canonical.get(role) or {}).get("review_state"),
                provenance_status=provenance_status,
                reason=resolution.get("reason") or f"{role}_canonical_value",
                evidence_refs=evidence_refs,
                source_signal="entities_canonical_v1.semantic_resolution_v1.people",
            )
        )
    return items


def _build_document_date_review_item(dm: DocumentMemory, canonical: Dict[str, Any]) -> List[Dict[str, Any]]:
    semantic = _canonical_semantic_resolution(dm, canonical)
    resolution = semantic.get("document_date") or {}
    legacy = canonical.get("document_date") or {}
    value = resolution.get("date_iso") or legacy.get("date_iso")
    if not value:
        return []

    evidence_refs = _normalize_evidence_refs(resolution.get("evidence_refs"))
    if not evidence_refs and legacy.get("evidence"):
        evidence_refs = [_normalize_evidence_ref_dict(legacy.get("evidence"))]
    provenance_status = (
        resolution.get("provenance_status")
        or (evidence_refs[0].get("provenance_status") if evidence_refs else None)
        or (legacy.get("evidence") or {}).get("provenance_status")
    )
    return [
        _make_review_item(
            item_type="document_date",
            field="document_date",
            value=value,
            confidence=resolution.get("confidence") or legacy.get("confidence"),
            review_state=resolution.get("review_state") or legacy.get("review_state"),
            provenance_status=provenance_status,
            reason=resolution.get("reason") or "document_date_canonical_value",
            evidence_refs=evidence_refs,
            source_signal="entities_canonical_v1.semantic_resolution_v1.document_date",
        )
    ]


def _build_cid_review_items(canonical: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for cid in ((canonical.get("clinical") or {}).get("cids") or []):
        if not isinstance(cid, dict) or not cid.get("code"):
            continue
        evidence = cid.get("evidence") or {}
        items.append(
            _make_review_item(
                item_type="clinical_code",
                field="cid",
                value=cid.get("code"),
                confidence=0.9 if evidence.get("bbox") else 0.7,
                review_state="auto_confirmed" if evidence.get("bbox") else "review_recommended",
                provenance_status=evidence.get("provenance_status"),
                reason="clinical_cid_detected",
                evidence_refs=[_normalize_evidence_ref_dict(evidence)],
                source_signal="entities_canonical_v1.clinical.cids",
            )
        )
    return items


def _build_event_review_items(dm: DocumentMemory, canonical: Dict[str, Any]) -> List[Dict[str, Any]]:
    del canonical
    items: List[Dict[str, Any]] = []
    for event in getattr(dm.layer3, "eventos_probatorios", None) or []:
        event_type = _get(event, "event_type")
        if not event_type:
            tipo_ev = _get(event, "tipo_evento")
            event_type = _get(tipo_ev, "valor")
        if not event_type:
            continue
        citations = _normalize_evidence_refs(_get(event, "citations") or _get(event, "evidencias_origem") or [])
        provenance_status = _get(event, "provenance_status")
        lacks_bbox = not any(citation.get("bbox") for citation in citations)
        if provenance_status not in {"estimated", "inferred"} and not lacks_bbox:
            continue
        items.append(
            _make_review_item(
                item_type="event",
                field=event_type,
                value={
                    "event_id": _get(event, "event_id"),
                    "event_type": event_type,
                    "date_iso": _get(event, "date_iso"),
                    "title": _get(event, "title") or _get(event, "descricao_curta"),
                },
                confidence=_get(event, "confidence", _get(event, "confianca")),
                review_state=_get(event, "review_state"),
                provenance_status=provenance_status or ("inferred" if lacks_bbox else None),
                reason=(
                    "estimated_probatory_event"
                    if provenance_status == "estimated"
                    else "inferred_probatory_event_without_exact_bbox"
                    if provenance_status == "inferred" or lacks_bbox
                    else "probatory_event_review"
                ),
                evidence_refs=citations,
                source_signal="layer3.eventos_probatorios",
                suggested_action=(
                    "confirm_estimated_event_bounds"
                    if provenance_status == "estimated"
                    else "confirm_event_with_exact_evidence"
                ),
            )
        )
    return items


def _build_seed_layer3_conflict_items(dm: DocumentMemory) -> List[Dict[str, Any]]:
    warning = build_timeline_consistency_warning(dm)
    if not warning:
        return []
    details = warning.get("details") or {}
    return [
        _make_review_item(
            item_type="conflict",
            field="timeline_seed_vs_layer3",
            value={
                "seed_event_count": details.get("seed_event_count"),
                "layer3_event_count": details.get("layer3_event_count"),
                "seed_dates": details.get("seed_dates"),
                "layer3_dates": details.get("layer3_dates"),
            },
            confidence=0.99,
            review_state="needs_review",
            provenance_status="conflict",
            reason=warning.get("code") or "timeline_seed_layer3_divergence",
            evidence_refs=[],
            source_signal="timeline_consistency_v1",
            suggested_action="reconcile_timeline_sources",
        )
    ]


def _build_canonical_layer3_conflict_items(dm: DocumentMemory, canonical: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    semantic = _canonical_semantic_resolution(dm, canonical)
    canonical_date = (semantic.get("document_date") or {}).get("date_iso") or (canonical.get("document_date") or {}).get("date_iso")
    if not canonical_date:
        return items

    event_dates = {
        _get(event, "date_iso")
        for event in getattr(dm.layer3, "eventos_probatorios", None) or []
        if _get(event, "event_type") == "document_issue_date" and _get(event, "date_iso")
    }
    if event_dates and canonical_date not in event_dates:
        evidence_refs = _normalize_evidence_refs((semantic.get("document_date") or {}).get("evidence_refs"))
        if not evidence_refs and (canonical.get("document_date") or {}).get("evidence"):
            evidence_refs = [_normalize_evidence_ref_dict((canonical.get("document_date") or {}).get("evidence"))]
        items.append(
            _make_review_item(
                item_type="conflict",
                field="document_date",
                value={
                    "canonical_document_date": canonical_date,
                    "layer3_document_issue_dates": sorted(event_dates),
                },
                confidence=0.99,
                review_state="needs_review",
                provenance_status="conflict",
                reason="canonical_document_date_differs_from_layer3_document_issue_date",
                evidence_refs=evidence_refs,
                source_signal="entities_canonical_v1.document_date",
                suggested_action="reconcile_document_date_sources",
            )
        )
    return items


def _build_review_items_v1(dm: DocumentMemory) -> Dict[str, Any]:
    canonical = _load_entities_canonical(dm)
    items = []
    items.extend(_build_people_review_items(dm, canonical))
    items.extend(_build_document_date_review_item(dm, canonical))
    items.extend(_build_cid_review_items(canonical))
    items.extend(_build_event_review_items(dm, canonical))
    items.extend(_build_canonical_layer3_conflict_items(dm, canonical))
    items.extend(_build_seed_layer3_conflict_items(dm))

    return {
        "version": "review_items_v1",
        "document_id": dm.layer0.documentid if dm.layer0 else None,
        "document_type": _canonical_document_type(dm),
        "artifact_uri": _artifact_uri(dm),
        "generated_at": _now_iso(),
        "total_items": len(items),
        "needs_review_count": sum(
            1 for item in items
            if item.get("review_state") in ("needs_review", "review_recommended")
        ),
        "items": items,
    }


# ─────────────────────────────────────────────────────────────────────────────
# apply_layer5
# ─────────────────────────────────────────────────────────────────────────────

def apply_layer5(dm: DocumentMemory) -> DocumentMemory:
    if isinstance(dm.layer5, dict):
        try:
            dm.layer5 = Layer5Derivatives(**dm.layer5)
        except Exception:
            dm.layer5 = Layer5Derivatives()
    elif not isinstance(dm.layer5, Layer5Derivatives):
        dm.layer5 = Layer5Derivatives()

    midia = dm.layer1.midia if dm.layer1 else None

    dm.layer5.imagens_derivadas = []
    dm.layer5.videos_derivados = []
    dm.layer5.audios_derivados = []
    dm.layer5.documentos_derivados = []

    if midia == MediaType.imagem:
        dm.layer5.imagens_derivadas.append(
            Derivado(tipo="thumbnail", uri="generated://thumbnail.jpg")
        )
    elif midia == MediaType.video:
        dm.layer5.videos_derivados.append(
            Derivado(tipo="frame_chave", uri="generated://frame.jpg")
        )
    elif midia == MediaType.audio:
        dm.layer5.audios_derivados.append(
            Derivado(tipo="waveform", uri="generated://waveform.png")
        )
    elif midia == MediaType.documento:
        dm.layer5.documentos_derivados.append(
            Derivado(tipo="preview", uri="generated://preview.pdf")
        )

    # Layer5 ainda não persiste derivados em backend real.
    # Mantemos URIs de placeholder explícitas para compatibilidade,
    # mas não afirmamos persistência nem expomos blob fake.
    dm.layer5.storage_uris = []
    dm.layer5.persistence_state = _PLACEHOLDER_PERSISTENCE_STATE

    if dm.layer3 is not None:
        dm.layer5.read_models = {
            "timeline_v1": _build_timeline_v1(dm),
            "entity_summary_v1": _build_entity_summary_v1(dm),
            "review_items_v1": _build_review_items_v1(dm),
        }

    return dm
