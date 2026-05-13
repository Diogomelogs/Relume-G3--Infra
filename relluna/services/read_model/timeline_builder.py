from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from relluna.core.document_memory import DocumentMemory
from relluna.services.evidence.signals import load_critical_signal_json


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _load_signal_json(dm: DocumentMemory, key: str) -> Optional[Any]:
    if key in {
        "page_evidence_v1",
        "page_unit_v1",
        "subdocument_unit_v1",
        "document_relation_graph_v1",
        "entities_canonical_v1",
        "timeline_seed_v2",
    } and isinstance(dm, DocumentMemory):
        return load_critical_signal_json(dm, key)
    layer2 = _get(dm, "layer2")
    if layer2 is None:
        return None
    sinais = _get(layer2, "sinais_documentais", {}) or {}
    s = sinais.get(key)
    if s is None:
        return None
    value = _get(s, "valor", s)
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
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
        event_type = item.get("event_type") or item.get("event_hint") or "evento_detectado"

        evidence = {
            "page": item.get("page"),
            "bbox": item.get("bbox"),
            "snippet": item.get("snippet"),
            "date_literal": item.get("date_literal"),
            "source_path": item.get("source_path"),
            "provenance_status": item.get("provenance_status"),
            "review_state": item.get("review_state"),
            "subdoc_id": item.get("subdoc_id"),
        }

        normalized.append(
            {
                "event_id": event_id,
                "date": date_iso,
                "label": event_type,
                "event_type": event_type,
                "subdoc_id": item.get("subdoc_id"),
                "title": item.get("title") or event_type,
                "description": item.get("description"),
                "confidence": item.get("confidence"),
                "review_state": item.get("review_state"),
                "provenance_status": item.get("provenance_status"),
                "assertion_level": item.get("assertion_level") or ("observed" if item.get("provenance_status") == "exact" else "inferred"),
                "warnings": item.get("warnings") or [],
                "uncertainties": item.get("uncertainties") or [],
                "contradiction_candidates": item.get("contradiction_candidates") or [],
                "entities": item.get("entities", {}),
                "citations": [],
                "artifact_uri": item.get("artifact_uri"),
                "evidence_navigation": {
                    "document_id": None,
                    "artifact_uri": item.get("artifact_uri"),
                    "page": item.get("page"),
                    "bbox": item.get("bbox"),
                    "snippet": item.get("snippet"),
                    "subdoc_id": item.get("subdoc_id"),
                },
                "evidence_ref": evidence,
            }
        )

    normalized.sort(key=lambda x: (x["date"], x.get("subdoc_id") or "", x["event_id"] or ""))
    return normalized


def _normalize_layer3_probatory_events(dm: DocumentMemory) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    layer3 = _get(dm, "layer3")

    for event in _get(layer3, "eventos_probatorios", []) or []:
        date_iso = _get(event, "date_iso")
        if not date_iso:
            continue

        event_type = _get(event, "event_type")
        if not event_type:
            tipo_ev = _get(event, "tipo_evento")
            event_type = _get(tipo_ev, "valor") if tipo_ev else None

        normalized.append(
            {
                "event_id": _get(event, "event_id"),
                "date": date_iso,
                "event_type": event_type or "evento_detectado",
                "subdoc_id": _get(event, "subdoc_id"),
            }
        )

    normalized.sort(key=lambda x: (x["date"], x.get("subdoc_id") or "", x["event_id"] or ""))
    return normalized


_SINGLETON_COMPATIBILITY_EVENT_TYPES = {
    "document_issue_date",
    "parecer_emitido",
}


def _reconcile_public_timeline_with_seed_fallback(
    layer3_timeline: List[Dict[str, Any]],
    timeline_seed_v2: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not layer3_timeline:
        return _normalize_timeline_items(timeline_seed_v2)
    if not timeline_seed_v2:
        return list(layer3_timeline)

    reconciled = [dict(event) for event in layer3_timeline if isinstance(event, dict)]
    normalized_seed_events = _normalize_timeline_items(timeline_seed_v2)
    exact_keys = {
        (event.get("subdoc_id"), event.get("event_type"), event.get("date"))
        for event in reconciled
    }
    singleton_indexes = {
        (event.get("subdoc_id"), event.get("event_type")): idx
        for idx, event in enumerate(reconciled)
        if event.get("event_type") in _SINGLETON_COMPATIBILITY_EVENT_TYPES
    }

    for seed_event in normalized_seed_events:
        exact_key = (
            seed_event.get("subdoc_id"),
            seed_event.get("event_type"),
            seed_event.get("date"),
        )
        if exact_key in exact_keys:
            continue

        singleton_key = (
            seed_event.get("subdoc_id"),
            seed_event.get("event_type"),
        )
        singleton_idx = singleton_indexes.get(singleton_key)
        if singleton_idx is not None:
            base_event = reconciled[singleton_idx]
            patched_event = dict(base_event)
            patched_event["date"] = seed_event.get("date")
            patched_event["evidence_ref"] = seed_event.get("evidence_ref", {})
            patched_event["evidence_navigation"] = dict(
                base_event.get("evidence_navigation") or {}
            )
            patched_event["evidence_navigation"]["page"] = seed_event.get(
                "evidence_navigation", {}
            ).get("page")
            patched_event["evidence_navigation"]["bbox"] = seed_event.get(
                "evidence_navigation", {}
            ).get("bbox")
            patched_event["evidence_navigation"]["snippet"] = seed_event.get(
                "evidence_navigation", {}
            ).get("snippet")
            patched_event["evidence_navigation"]["subdoc_id"] = seed_event.get(
                "evidence_navigation", {}
            ).get("subdoc_id") or patched_event.get("subdoc_id")
            patched_event["artifact_uri"] = (
                base_event.get("artifact_uri") or seed_event.get("artifact_uri")
            )
            patched_event["assertion_level"] = (
                seed_event.get("assertion_level") or patched_event.get("assertion_level")
            )
            if not patched_event.get("citations"):
                patched_event["citations"] = seed_event.get("citations") or []
            patched_event.setdefault("compatibility_bridge", {})
            patched_event["compatibility_bridge"]["seed_repaired_date"] = True
            patched_event["compatibility_bridge"]["seed_date"] = seed_event.get("date")
            patched_event["compatibility_bridge"]["seed_event_id"] = seed_event.get("event_id")
            reconciled[singleton_idx] = patched_event
            exact_keys.add(exact_key)
            continue

        reconciled.append(seed_event)
        exact_keys.add(exact_key)

    reconciled.sort(key=lambda x: (x["date"], x.get("subdoc_id") or "", x["event_id"] or ""))
    return reconciled


def _first_event_evidence_ref(event: Any) -> Dict[str, Any]:
    citations = _get(event, "citations", None) or _get(event, "evidencias_origem", None) or []
    citation = citations[0] if citations else None

    return {
        "page": _get(citation, "page"),
        "bbox": _get(citation, "bbox"),
        "snippet": _get(citation, "snippet"),
        "date_literal": _get(citation, "date_literal"),
        "source_path": _get(citation, "source_path"),
        "provenance_status": _get(citation, "provenance_status"),
        "review_state": _get(citation, "review_state"),
        "subdoc_id": _get(citation, "subdoc_id") or _get(event, "subdoc_id"),
    }


def _citation_to_public_dict(citation: Any) -> Dict[str, Any]:
    return {
        "source_path": _get(citation, "source_path"),
        "page": _get(citation, "page"),
        "bbox": _get(citation, "bbox"),
        "snippet": _get(citation, "snippet"),
        "date_literal": _get(citation, "date_literal"),
        "confidence": _get(citation, "confidence"),
        "provenance_status": _get(citation, "provenance_status"),
        "review_state": _get(citation, "review_state"),
        "note": _get(citation, "note"),
        "subdoc_id": _get(citation, "subdoc_id"),
    }


def _canonical_subdocument_metadata(dm: DocumentMemory) -> Dict[str, Any]:
    canonical = _load_signal_json(dm, "entities_canonical_v1") or {}
    if not isinstance(canonical, dict):
        return {}

    subdocuments = canonical.get("subdocuments") or []
    aggregate = canonical.get("aggregate_projection_v1") or {}
    if not isinstance(subdocuments, list) or not subdocuments:
        return {}

    return {
        "has_subdocuments": True,
        "subdocument_count": len([item for item in subdocuments if isinstance(item, dict)]),
        "aggregate_projection_v1": aggregate if isinstance(aggregate, dict) else {},
    }


def _artifact_navigation_uri(dm: DocumentMemory) -> Optional[str]:
    layer1 = _get(dm, "layer1")
    artefatos = _get(layer1, "artefatos", []) or []
    if not artefatos:
        return None

    original = next((item for item in artefatos if _get(item, "tipo") == "original"), None)
    artifact = original or artefatos[0]
    return _get(artifact, "uri")


def adapt_layer3_probatory_events_to_public_timeline(dm: DocumentMemory) -> List[Dict[str, Any]]:
    timeline: List[Dict[str, Any]] = []
    layer3 = _get(dm, "layer3")
    document_id = _get(_get(dm, "layer0"), "documentid")
    artifact_uri = _artifact_navigation_uri(dm)

    for event in _get(layer3, "eventos_probatorios", []) or []:
        date_iso = _get(event, "date_iso")
        if not date_iso:
            continue

        event_type = _get(event, "event_type")
        if not event_type:
            tipo_ev = _get(event, "tipo_evento")
            event_type = _get(tipo_ev, "valor") if tipo_ev else None
        event_type = event_type or "evento_detectado"
        citations = _get(event, "citations", None) or _get(event, "evidencias_origem", None) or []
        title = _get(event, "title") or _get(event, "descricao_curta") or event_type
        description = _get(event, "description") or _get(event, "descricao_curta")

        timeline.append(
            {
                "event_id": _get(event, "event_id"),
                "date": date_iso,
                "label": event_type,
                "event_type": event_type,
                "subdoc_id": _get(event, "subdoc_id"),
                "title": title,
                "description": description,
                "confidence": _get(event, "confidence", _get(event, "confianca")),
                "review_state": _get(event, "review_state"),
                "provenance_status": _get(event, "provenance_status"),
                "assertion_level": _get(event, "assertion_level") or ("observed" if _get(event, "provenance_status") == "exact" else "inferred"),
                "warnings": _get(event, "warnings", []) or [],
                "uncertainties": _get(event, "uncertainties", []) or [],
                "contradiction_candidates": _get(event, "contradiction_candidates", []) or [],
                "entities": _get(event, "entities", {}) or {},
                "citations": [_citation_to_public_dict(citation) for citation in citations],
                "artifact_uri": artifact_uri,
                "evidence_navigation": {
                    "document_id": document_id,
                    "artifact_uri": artifact_uri,
                    "page": _get(citations[0], "page") if citations else None,
                    "bbox": _get(citations[0], "bbox") if citations else None,
                    "snippet": _get(citations[0], "snippet") if citations else None,
                    "subdoc_id": _get(citations[0], "subdoc_id") if citations else _get(event, "subdoc_id"),
                },
                "evidence_ref": _first_event_evidence_ref(event),
            }
        )

    timeline.sort(key=lambda x: (x["date"], x.get("subdoc_id") or "", x["event_id"] or ""))
    return timeline


def _segmented_subdocuments(dm: DocumentMemory) -> List[Dict[str, Any]]:
    units = _load_signal_json(dm, "subdocument_unit_v1") or []
    if not isinstance(units, list):
        return []
    out: List[Dict[str, Any]] = []
    for unit in units:
        if not isinstance(unit, dict):
            continue
        out.append(
            {
                "subdoc_id": unit.get("subdoc_id"),
                "pages": unit.get("pages") or [],
                "document_type": unit.get("document_type"),
                "patient": ((unit.get("patient") or {}).get("name")),
                "provider": ((unit.get("provider") or {}).get("name")),
                "document_date": ((unit.get("document_date") or {}).get("date_iso")),
                "warnings": unit.get("warnings") or [],
                "uncertainties": unit.get("uncertainties") or [],
                "confidence": unit.get("confidence") or {},
            }
        )
    return out


def _relation_graph(dm: DocumentMemory) -> Dict[str, Any]:
    graph = _load_signal_json(dm, "document_relation_graph_v1") or {}
    return graph if isinstance(graph, dict) else {}


def build_timeline_consistency_warning(dm: DocumentMemory) -> Optional[Dict[str, Any]]:
    timeline_v2 = _load_signal_json(dm, "timeline_seed_v2") or []
    if not isinstance(timeline_v2, list):
        timeline_v2 = []

    seed_events = _normalize_timeline_items(timeline_v2)
    layer3_events = _normalize_layer3_probatory_events(dm)

    if not seed_events and not layer3_events:
        return None

    seed_dates = [event["date"] for event in seed_events]
    layer3_dates = [event["date"] for event in layer3_events]
    seed_keys = [
        (event.get("subdoc_id"), event.get("event_type"), event["date"])
        for event in seed_events
    ]
    layer3_keys = [
        (event.get("subdoc_id"), event.get("event_type"), event["date"])
        for event in layer3_events
    ]
    count_matches = len(seed_events) == len(layer3_events)
    dates_match = seed_dates == layer3_dates and seed_keys == layer3_keys

    if count_matches and dates_match:
        return None

    return {
        "code": "timeline_seed_v2_layer3_divergence",
        "severity": "warning",
        "source": "timeline_consistency_v1",
        "message": (
            "timeline_seed_v2 diverge de Layer3.eventos_probatorios em "
            "contagem de eventos ou datas principais."
        ),
        "details": {
            "seed_event_count": len(seed_events),
            "layer3_event_count": len(layer3_events),
            "seed_dates": seed_dates,
            "layer3_dates": layer3_dates,
            "seed_keys": seed_keys,
            "layer3_keys": layer3_keys,
            "count_matches": count_matches,
            "dates_match": dates_match,
        },
    }


def build_document_timeline_read_model(dm: DocumentMemory) -> Dict[str, Any]:
    """
    Read model por documento.
    Prioridade:
    1. Layer3.eventos_probatorios
    2. timeline_seed_v2
    3. timeline_seed_v1
    """
    l0 = dm.layer0
    l1 = dm.layer1

    timeline_v2 = _load_signal_json(dm, "timeline_seed_v2") or []
    timeline_v1 = _load_signal_json(dm, "timeline_seed_v1") or []
    layer3_timeline = adapt_layer3_probatory_events_to_public_timeline(dm)
    hard_entities = (
        _load_signal_json(dm, "hard_entities_v2")
        or _load_signal_json(dm, "hard_entities_v1")
        or []
    )
    artifact_uri = _artifact_navigation_uri(dm)

    timeline_raw = timeline_v2 if timeline_v2 else timeline_v1
    timeline = _reconcile_public_timeline_with_seed_fallback(layer3_timeline, timeline_v2)
    if not timeline:
        timeline = _normalize_timeline_items(timeline_raw)
    canonical_meta = _canonical_subdocument_metadata(dm)
    segmented_subdocuments = _segmented_subdocuments(dm)
    relation_graph = _relation_graph(dm)
    document_id = getattr(l0, "documentid", None)
    for event in timeline:
        if not event.get("artifact_uri"):
            event["artifact_uri"] = artifact_uri
        navigation = event.setdefault("evidence_navigation", {})
        if navigation.get("document_id") is None:
            navigation["document_id"] = document_id
        if navigation.get("artifact_uri") is None:
            navigation["artifact_uri"] = artifact_uri
        if navigation.get("page") is None:
            navigation["page"] = event.get("evidence_ref", {}).get("page")
        if navigation.get("bbox") is None:
            navigation["bbox"] = event.get("evidence_ref", {}).get("bbox")
        if navigation.get("snippet") is None:
            navigation["snippet"] = event.get("evidence_ref", {}).get("snippet")
        if navigation.get("subdoc_id") is None:
            navigation["subdoc_id"] = (
                event.get("evidence_ref", {}).get("subdoc_id") or event.get("subdoc_id")
            )
    consistency_warning = build_timeline_consistency_warning(dm)
    warnings = [consistency_warning] if consistency_warning else []
    if canonical_meta.get("has_subdocuments"):
        warnings.append(
            {
                "code": "entities_canonical_v1_global_is_compatibility_aggregate",
                "severity": "info",
                "source": "timeline_read_model_v2",
                "message": (
                    "entities_canonical_v1 global é uma projeção agregada de compatibilidade; "
                    "subdocuments é a fonte semântica mais autoritativa quando presente."
                ),
                "details": {
                    "subdocument_count": canonical_meta.get("subdocument_count"),
                    "aggregate_projection_v1": canonical_meta.get("aggregate_projection_v1") or {},
                },
            }
        )
    graph_edges = relation_graph.get("edges") or []
    graph_inconsistencies = [
        edge
        for edge in graph_edges
        if edge.get("relation_type") in {"conflict", "unknown"}
    ]
    warnings.extend(
        {
            "code": f"document_relation_graph_{edge.get('relation_type')}",
            "severity": "warning" if edge.get("relation_type") == "conflict" else "info",
            "source": "document_relation_graph_v1",
            "message": (
                "Subdocumentos com conflito explícito de identidade/contexto."
                if edge.get("relation_type") == "conflict"
                else "Relação entre subdocumentos permaneceu unknown por evidência insuficiente."
            ),
            "details": edge,
        }
        for edge in graph_inconsistencies
    )

    anchored_events = sum(
        1
        for ev in timeline
        if ev.get("evidence_ref", {}).get("page") is not None
        and ev.get("evidence_ref", {}).get("bbox") is not None
    )
    needs_review_count = sum(
        1
        for ev in timeline
        if ev.get("review_state") in ("needs_review", "review_recommended")
    )
    observed_events = sum(1 for ev in timeline if ev.get("assertion_level") == "observed")
    inferred_events = sum(1 for ev in timeline if ev.get("assertion_level") == "inferred")
    unknown_events = sum(1 for ev in timeline if ev.get("assertion_level") == "unknown")

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
            "artifact_uri": artifact_uri,
        },
        "summary": {
            "total_events": len(timeline),
            "needs_review_count": needs_review_count,
            "anchored_events": anchored_events,
            "hard_entities_count": len(hard_entities),
            "has_subdocuments": bool(canonical_meta.get("has_subdocuments")) or bool(segmented_subdocuments),
            "subdocument_count": canonical_meta.get("subdocument_count") or len(segmented_subdocuments),
            "observed_events": observed_events,
            "inferred_events": inferred_events,
            "unknown_events": unknown_events,
            "relation_conflict_count": sum(1 for edge in graph_edges if edge.get("relation_type") == "conflict"),
            "relation_unknown_count": sum(1 for edge in graph_edges if edge.get("relation_type") == "unknown"),
            "timeline_consistency_score": 0.0 if consistency_warning else 100.0,
            "warnings": warnings,
        },
        "warnings": warnings,
        "inconsistencies": graph_inconsistencies,
        "subdocuments": segmented_subdocuments,
        "relations": relation_graph,
        "timeline": timeline,
        "hard_entities": hard_entities,
    }
