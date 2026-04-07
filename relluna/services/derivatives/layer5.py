from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from relluna.core.document_memory import DocumentMemory, MediaType
from relluna.core.contracts.document_memory_contract import (
    Layer5Derivatives,
    Derivado,
    StorageURI,
)

_BUILDER_VERSION = "layer5_read_model_v3"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _review_state(confidence: Optional[float]) -> str:
    c = confidence or 0.0
    if c >= 0.95:
        return "auto_confirmed"
    if c >= 0.80:
        return "review_recommended"
    return "needs_review"


def _load_signal_json(dm: DocumentMemory, key: str) -> Any:
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
        crm = ((canonical.get("provider") or {}).get("crm") or {})
        display = crm.get("display")
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

    events_out.sort(key=_event_sort_key)

    return {
        "version": _BUILDER_VERSION,
        "document_id": document_id,
        "document_type": document_type,
        "generated_at": _now_iso(),
        "total_events": len(events_out),
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

    crm = ((canonical.get("provider") or {}).get("crm") or {})
    crms = [crm.get("display")] if crm.get("display") else []

    return {
        "patient": patient,
        "mother": mother,
        "provider": provider,
        "cids": cids,
        "crms": crms,
    }


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

    dm.layer5.storage_uris = [StorageURI(uri="https://local.blob/fake", kind="blob")]
    dm.layer5.persistence_state = "stored"

    if dm.layer3 is not None:
        dm.layer5.read_models = {
            "timeline_v1": _build_timeline_v1(dm),
            "entity_summary_v1": _build_entity_summary_v1(dm),
        }

    return dm