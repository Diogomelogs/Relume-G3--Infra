from __future__ import annotations

from typing import Any, Dict, List, Optional

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.types_basic import ProvenancedString
from relluna.domain.legal_fields import CanonicalExtraction, CanonicalField, EvidenceAnchor
from relluna.services.evidence.signals import dump_critical_signal_json, load_critical_signal_json

FONTE = "services.legal.legal_canonical_fields_v1"
SIGNAL_KEY = "legal_canonical_fields_v1"
SOURCE_SIGNAL = "entities_canonical_v1"
SOURCE_PATH = "layer2.sinais_documentais.entities_canonical_v1"


def _normalized_text(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return " ".join(value.split()) or None
    return value


def _anchor_from_evidence(evidence: Dict[str, Any]) -> EvidenceAnchor:
    bbox = evidence.get("bbox")
    bbox_out: Optional[List[float]] = None
    if isinstance(bbox, list):
        try:
            bbox_out = [float(item) for item in bbox]
        except Exception:
            bbox_out = None
    return EvidenceAnchor(
        page=evidence.get("page"),
        bbox=bbox_out,
        snippet=evidence.get("snippet"),
    )


def _evidence_refs(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    refs = block.get("evidence_refs")
    if isinstance(refs, list) and refs:
        return [item for item in refs if isinstance(item, dict)]
    evidence = block.get("evidence")
    if isinstance(evidence, dict) and evidence:
        return [evidence]
    return []


def _field(
    *,
    name: str,
    value: Any,
    normalized_value: Any,
    doc_type: str,
    confidence: float,
    assertion_level: str,
    provenance_status: Optional[str],
    review_state: Optional[str],
    evidence: Optional[Dict[str, Any]],
    evidence_refs: Optional[List[Dict[str, Any]]] = None,
    reason: Optional[str] = None,
) -> CanonicalField:
    evidence = evidence or {}
    return CanonicalField(
        name=name,
        value=value,
        normalized_value=normalized_value,
        confidence=confidence,
        source_doc_type=doc_type,
        anchor=_anchor_from_evidence(evidence),
        assertion_level=assertion_level,
        provenance_status=provenance_status,
        review_state=review_state,
        source_signal=SOURCE_SIGNAL,
        source_path=evidence.get("source_path") or SOURCE_PATH,
        evidence_refs=evidence_refs or ([evidence] if evidence else []),
        reason=reason,
    )


def _append_person_field(fields: List[CanonicalField], name: str, block: Dict[str, Any], doc_type: str) -> None:
    if not isinstance(block, dict):
        return
    person_name = _normalized_text(block.get("name"))
    if not person_name:
        return
    evidence = block.get("evidence") or {}
    fields.append(
        _field(
            name=name,
            value=person_name,
            normalized_value=person_name,
            doc_type=doc_type,
            confidence=float(block.get("confidence") or 0.0),
            assertion_level="observed",
            provenance_status=evidence.get("provenance_status") or ("exact" if evidence.get("bbox") else "snippet_only"),
            review_state=block.get("review_state") or "review_recommended",
            evidence=evidence,
            evidence_refs=_evidence_refs(block),
            reason=((block.get("resolution") or {}).get("reason")),
        )
    )


def _append_document_type_field(fields: List[CanonicalField], canonical: Dict[str, Any], doc_type: str) -> None:
    if not doc_type:
        return
    quality = canonical.get("quality") or {}
    review_state = "review_recommended" if quality.get("warnings") else "auto_confirmed"
    fields.append(
        _field(
            name="Tipo_Documento",
            value=doc_type,
            normalized_value=doc_type,
            doc_type=doc_type,
            confidence=0.9,
            assertion_level="inferred",
            provenance_status="inferred",
            review_state=review_state,
            evidence={},
            evidence_refs=[],
            reason="document_type_projection_from_entities_canonical_v1",
        )
    )


def _append_document_date_field(fields: List[CanonicalField], block: Dict[str, Any], doc_type: str) -> None:
    if not isinstance(block, dict):
        return
    date_iso = block.get("date_iso")
    if not date_iso:
        return
    evidence = block.get("evidence") or {}
    fields.append(
        _field(
            name="Data_Documento",
            value=block.get("literal") or date_iso,
            normalized_value=date_iso,
            doc_type=doc_type,
            confidence=float(block.get("confidence") or 0.0),
            assertion_level="observed",
            provenance_status=evidence.get("provenance_status") or ("exact" if evidence.get("bbox") else "snippet_only"),
            review_state=block.get("review_state") or "review_recommended",
            evidence=evidence,
            evidence_refs=_evidence_refs(block),
            reason=((block.get("resolution") or {}).get("reason")),
        )
    )


def _append_cid_fields(fields: List[CanonicalField], clinical: Dict[str, Any], doc_type: str) -> None:
    if not isinstance(clinical, dict):
        return
    cids = [item for item in (clinical.get("cids") or []) if isinstance(item, dict) and item.get("code")]
    for item in cids:
        evidence = item.get("evidence") or {}
        code = _normalized_text(item.get("code"))
        fields.append(
            _field(
                name="CID_Atestado",
                value=code,
                normalized_value=code,
                doc_type=doc_type,
                confidence=float(item.get("confidence") or 0.0),
                assertion_level="observed",
                provenance_status=evidence.get("provenance_status") or ("exact" if evidence.get("bbox") else "snippet_only"),
                review_state=item.get("review_state") or "review_recommended",
                evidence=evidence,
                evidence_refs=[evidence] if evidence else [],
                reason="clinical_cid_from_entities_canonical_v1",
            )
        )


def _append_medical_range_fields(fields: List[CanonicalField], canonical: Dict[str, Any], doc_type: str) -> None:
    internacao = canonical.get("internacao") or {}
    for field_name, block in (
        ("Internacao_Inicio", internacao.get("start") or {}),
        ("Internacao_Fim", internacao.get("end") or {}),
    ):
        if not isinstance(block, dict) or not block.get("date_iso"):
            continue
        evidence = block.get("evidence") or {}
        fields.append(
            _field(
                name=field_name,
                value=block.get("literal") or block.get("date_iso"),
                normalized_value=block.get("date_iso"),
                doc_type=doc_type,
                confidence=float(block.get("confidence") or 0.0),
                assertion_level="observed",
                provenance_status=evidence.get("provenance_status") or "text_fallback",
                review_state=block.get("review_state") or "review_recommended",
                evidence=evidence,
                evidence_refs=[evidence] if evidence else [],
                reason="medical_range_from_entities_canonical_v1",
            )
        )

    afastamento = canonical.get("afastamento") or {}
    duration = afastamento.get("duration_days") or {}
    if duration.get("value") is not None:
        fields.append(
            _field(
                name="Dias_Afastamento",
                value=duration.get("value"),
                normalized_value=duration.get("value"),
                doc_type=doc_type,
                confidence=float(duration.get("confidence") or 0.0),
                assertion_level="observed",
                provenance_status="text_fallback",
                review_state="review_recommended",
                evidence={},
                evidence_refs=[],
                reason="afastamento_duration_from_entities_canonical_v1",
            )
        )

    for field_name, block, assertion_level in (
        ("Afastamento_Inicio", afastamento.get("start") or {}, "inferred"),
        ("Afastamento_Fim_Estimado", afastamento.get("estimated_end") or {}, "estimated"),
    ):
        if not isinstance(block, dict) or not block.get("date_iso"):
            continue
        evidence = block.get("evidence") or {}
        fields.append(
            _field(
                name=field_name,
                value=block.get("literal") or block.get("date_iso"),
                normalized_value=block.get("date_iso"),
                doc_type=doc_type,
                confidence=float(block.get("confidence") or 0.0),
                assertion_level=assertion_level,
                provenance_status=evidence.get("provenance_status") or assertion_level,
                review_state=block.get("review_state") or "review_recommended",
                evidence=evidence,
                evidence_refs=[evidence] if evidence else [],
                reason="afastamento_projection_from_entities_canonical_v1",
            )
        )


def build_legal_canonical_extraction(
    dm: DocumentMemory,
    canonical: Optional[Dict[str, Any]] = None,
) -> Optional[CanonicalExtraction]:
    canonical = canonical or load_critical_signal_json(dm, SOURCE_SIGNAL) or {}
    if not isinstance(canonical, dict) or not canonical:
        return None

    doc_type = _normalized_text(canonical.get("document_type")) or "documento_composto"
    fields: List[CanonicalField] = []

    _append_document_type_field(fields, canonical, doc_type)
    _append_person_field(fields, "Nome_Paciente", canonical.get("patient") or {}, doc_type)
    _append_person_field(fields, "Nome_Mae", canonical.get("mother") or {}, doc_type)
    _append_person_field(fields, "Nome_Prestador", canonical.get("provider") or {}, doc_type)

    provider = canonical.get("provider") or {}
    provider_evidence = provider.get("evidence") or {}
    if provider.get("crm"):
        fields.append(
            _field(
                name="CRM_Medico",
                value=provider.get("crm"),
                normalized_value=_normalized_text(provider.get("crm")),
                doc_type=doc_type,
                confidence=float(provider.get("confidence") or 0.0),
                assertion_level="observed",
                provenance_status=provider_evidence.get("provenance_status") or ("exact" if provider_evidence.get("bbox") else "snippet_only"),
                review_state=provider.get("review_state") or "review_recommended",
                evidence=provider_evidence,
                evidence_refs=_evidence_refs(provider),
                reason=((provider.get("resolution") or {}).get("reason")),
            )
        )

    _append_document_date_field(fields, canonical.get("document_date") or {}, doc_type)
    _append_cid_fields(fields, canonical.get("clinical") or {}, doc_type)
    _append_medical_range_fields(fields, canonical, doc_type)

    if not fields:
        return None

    return CanonicalExtraction(
        document_id=str(getattr(getattr(dm, "layer0", None), "documentid", "") or ""),
        doc_type=doc_type,
        confidence=max((field.confidence for field in fields), default=0.0),
        fields=fields,
        source_signal=SOURCE_SIGNAL,
        source_path=SOURCE_PATH,
        warnings=list((canonical.get("quality") or {}).get("warnings") or []),
    )


def apply_legal_canonical_fields_v1(
    dm: DocumentMemory,
    canonical: Optional[Dict[str, Any]] = None,
) -> DocumentMemory:
    if dm.layer2 is None:
        return dm

    extraction = build_legal_canonical_extraction(dm, canonical=canonical)
    if extraction is None:
        return dm

    dm.layer2.sinais_documentais[SIGNAL_KEY] = ProvenancedString(
        valor=dump_critical_signal_json(SIGNAL_KEY, extraction.model_dump(mode="json"), dm=dm),
        fonte=FONTE,
        metodo="entities_canonical_projection_v1",
        estado="confirmado",
        confianca=1.0,
    )
    return dm
