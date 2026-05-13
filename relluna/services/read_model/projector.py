from __future__ import annotations

from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from relluna.core.document_memory import (
    DocumentMemory,
    Layer4SemanticNormalization,
)
from relluna.services.derivatives.layer5 import apply_layer5
from relluna.services.read_model.models import DocumentReadModel
from relluna.services.read_model.store import ReadModelStore
from relluna.services.read_model.timeline_builder import build_document_timeline_read_model


def _layer4_date_str(l4: Layer4SemanticNormalization) -> Optional[str]:
    dc = l4.data_canonica
    if isinstance(dc, datetime):
        return dc.strftime("%Y-%m-%d")
    if isinstance(dc, str):
        return dc[:10]
    return None


def _safe_text(valor) -> Optional[str]:
    if valor and isinstance(valor, str):
        return valor.strip()
    return None


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if "." in key:
        current = obj
        for part in key.split("."):
            current = _get(current, part, None)
            if current is None:
                return default
        return current
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_layer4(dm: DocumentMemory) -> Optional[Layer4SemanticNormalization]:
    if isinstance(dm.layer4, Layer4SemanticNormalization):
        return dm.layer4
    if isinstance(dm.layer4, dict) and dm.layer4:
        try:
            return Layer4SemanticNormalization.model_validate(dm.layer4)
        except Exception:
            return None
    return None


def _original_artefact_uri(dm: DocumentMemory) -> Optional[str]:
    artefacts = getattr(dm.layer1, "artefatos", None) or []
    if not artefacts:
        return None
    original = next((item for item in artefacts if getattr(item, "tipo", None) == "original"), None)
    return getattr((original or artefacts[0]), "uri", None)


def _title_for_panel(dm: DocumentMemory, doc_type: Optional[str], patient: Optional[str]) -> str:
    if doc_type and patient:
        return f"{doc_type.replace('_', ' ')} - {patient}"
    if doc_type:
        return doc_type.replace("_", " ")
    if dm.layer1:
        return f"{dm.layer1.midia.value} {dm.layer0.documentid[:8]}"
    return dm.layer0.documentid


def _short_executive_summary(
    doc_type: Optional[str],
    patient: Optional[str],
    provider: Optional[str],
    cids: List[str],
    date_canonical: Optional[str],
    total_events: int,
    needs_review_count: int,
) -> str:
    parts: List[str] = []
    if doc_type:
        parts.append(doc_type.replace("_", " "))
    if patient:
        parts.append(f"paciente {patient}")
    if provider:
        parts.append(f"prestador {provider}")
    if cids:
        parts.append(f"CID {', '.join(cids[:3])}")
    if date_canonical:
        parts.append(f"data canônica {date_canonical}")
    if total_events:
        parts.append(f"{total_events} eventos na timeline")
    if needs_review_count:
        parts.append(f"{needs_review_count} itens pedem revisão")
    return "; ".join(parts) if parts else "Documento processado"


def project_dm_to_read_model(dm: DocumentMemory) -> DocumentReadModel:
    document_id = dm.layer0.documentid
    media_type = dm.layer1.midia.value if dm.layer1 else None

    # ---------------------------
    # Layer4 (canônico)
    # ---------------------------
    date_canonical: Optional[str] = None
    period_label: Optional[str] = None
    tags: List[str] = []
    entities: List[dict] = []
    layer4 = _as_layer4(dm)

    if layer4 is not None:
        date_canonical = _layer4_date_str(layer4)
        period_label = layer4.periodo
        tags = list(layer4.tags or [])

        for ent in layer4.entidades or []:
            entities.append(
                {
                    "kind": ent.kind,
                    "label": ent.label,
                }
            )

    if dm.layer5 is None or not getattr(dm.layer5, "read_models", None):
        dm = apply_layer5(dm)

    timeline_public = build_document_timeline_read_model(dm)
    layer5_read_models = getattr(dm.layer5, "read_models", None) or {}
    timeline_rm = layer5_read_models.get("timeline_v1") or {}
    entity_summary = layer5_read_models.get("entity_summary_v1") or {}
    review_items = layer5_read_models.get("review_items_v1") or {}

    patient = _safe_text(_get(entity_summary, "people.patient"))
    provider = _safe_text(_get(entity_summary, "people.provider"))
    cids = [str(cid) for cid in (_get(entity_summary, "clinical.cids", []) or []) if cid]
    doc_type = (
        _safe_text(_get(timeline_rm, "document_type"))
        or _safe_text(_get(review_items, "document_type"))
        or _safe_text(_get(dm.layer3, "tipo_documento.valor"))
    )
    event_types = list(dict.fromkeys(
        str(item.get("event_type"))
        for item in (_get(timeline_rm, "events", []) or [])
        if isinstance(item, dict) and item.get("event_type")
    ))
    needs_review_count = int(
        _get(review_items, "needs_review_count", None)
        or _get(timeline_rm, "needs_review_count", None)
        or _get(timeline_public, "summary.needs_review_count", 0)
        or 0
    )

    semantic_tags = list(dict.fromkeys(tags + [f"cid:{cid}" for cid in cids] + [f"event:{event_type}" for event_type in event_types]))
    tags = semantic_tags

    if patient:
        entities.append({"kind": "patient", "label": patient, "confidence": None})
    if provider:
        entities.append({"kind": "provider", "label": provider, "confidence": None})
    for cid in cids:
        entities.append({"kind": "cid", "label": cid, "confidence": None})

    dedup_entities: List[Dict[str, Any]] = []
    seen_entities = set()
    for entity in entities:
        key = (entity.get("kind"), entity.get("label"))
        if key in seen_entities or not entity.get("label"):
            continue
        seen_entities.add(key)
        dedup_entities.append(entity)
    entities = dedup_entities

    title = _title_for_panel(dm, doc_type, patient)
    summary = _short_executive_summary(
        doc_type,
        patient,
        provider,
        cids,
        date_canonical,
        int(_get(timeline_public, "summary.total_events", 0) or 0),
        needs_review_count,
    )

    # ---------------------------
    # TEXTO BASE (Layer2)
    # ---------------------------
    ocr_text = None
    transcription_text = None

    if dm.layer2:
        if getattr(dm.layer2, "texto_ocr_literal", None):
            ocr_text = _safe_text(dm.layer2.texto_ocr_literal.valor)

        if getattr(dm.layer2, "transcricao_literal", None):
            transcription_text = _safe_text(dm.layer2.transcricao_literal.valor)

    # ---------------------------
    # search_text (nunca vazio)
    # ---------------------------
    parts = [document_id, title, summary]

    if date_canonical:
        parts.append(date_canonical)

    if tags:
        parts.extend(tags)

    if entities:
        parts.extend(e["label"] for e in entities)

    if patient:
        parts.append(patient)
    if provider:
        parts.append(provider)
    if cids:
        parts.extend(cids)
    if event_types:
        parts.extend(event_types)

    if ocr_text:
        parts.append(ocr_text)

    if transcription_text:
        parts.append(transcription_text)

    search_text = " ".join(str(p) for p in parts if p) or document_id

    now = datetime.now(UTC)

    return DocumentReadModel(
        document_id=document_id,
        media_type=media_type,
        title=title,
        summary=summary,
        date_canonical=date_canonical,
        period_label=period_label,
        tags=tags,
        entities=entities,
        event_types=event_types,
        patient=patient,
        provider=provider,
        cids=cids,
        artefacts={"original": _original_artefact_uri(dm)} if _original_artefact_uri(dm) else {},
        timeline={
            "endpoint": f"/documents/{document_id}/timeline",
            "total_events": int(_get(timeline_public, "summary.total_events", 0) or 0),
            "anchored_events": int(_get(timeline_public, "summary.anchored_events", 0) or 0),
            "timeline_consistency_score": _get(timeline_public, "summary.timeline_consistency_score"),
        },
        confidence_indicators={
            "timeline_consistency_score": _get(timeline_public, "summary.timeline_consistency_score"),
            "needs_review_count": needs_review_count,
            "total_review_items": int(_get(review_items, "total_items", 0) or 0),
            "anchored_events": int(_get(timeline_public, "summary.anchored_events", 0) or 0),
        },
        needs_review_count=needs_review_count,
        doc_type=doc_type,
        search_text=search_text,
        created_at=now,
        updated_at=now,
    )


async def persist_document_read_model(dm: DocumentMemory) -> DocumentReadModel:
    read_model = project_dm_to_read_model(dm)
    store = ReadModelStore()
    await store.upsert(read_model)
    return read_model
