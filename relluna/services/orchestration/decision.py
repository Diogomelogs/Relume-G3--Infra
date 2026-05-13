from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Literal, Optional


ProcessingMode = Literal["fast", "standard", "forensic"]


@dataclass
class ProcessingDecision:
    mode: ProcessingMode
    reasons: List[str]
    confidence: float


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def decide_processing_mode(sig) -> ProcessingDecision:
    if sig.media_type in {"audio", "video"}:
        return ProcessingDecision(
            mode="forensic",
            reasons=["temporal_media_requires_transcription"],
            confidence=0.95,
        )

    if sig.media_type != "documento":
        return ProcessingDecision(
            mode="standard",
            reasons=["non_document_media"],
            confidence=0.90,
        )

    if sig.is_pdf and sig.page_count <= 2 and sig.has_native_text and sig.native_rotation == 0:
        return ProcessingDecision(
            mode="fast",
            reasons=["simple_pdf_with_native_text"],
            confidence=0.95,
        )

    if sig.is_pdf and (sig.native_rotation % 360) != 0:
        return ProcessingDecision(
            mode="forensic",
            reasons=["rotated_pdf_requires_heavier_path"],
            confidence=0.93,
        )

    if sig.is_pdf and not sig.has_native_text:
        return ProcessingDecision(
            mode="standard",
            reasons=["pdf_without_native_text_requires_ocr"],
            confidence=0.92,
        )

    return ProcessingDecision(
        mode="standard",
        reasons=["default_document_path"],
        confidence=0.90,
    )


def _load_json_signal(dm, key: str):
    layer2 = getattr(dm, "layer2", None)
    if layer2 is None:
        return None
    sinais = getattr(layer2, "sinais_documentais", {}) or {}
    sig = sinais.get(key)
    if not sig or not getattr(sig, "valor", None):
        return None
    try:
        return json.loads(sig.valor)
    except Exception:
        return None


def _has_clinical_markers(dm) -> bool:
    layer2 = getattr(dm, "layer2", None)
    text_signal = getattr(layer2, "texto_ocr_literal", None) if layer2 is not None else None
    text = (getattr(text_signal, "valor", "") or "").lower()
    if not text:
        return False
    return any(term in text for term in ["cid", "crm", "atestado", "internado", "diagnost", "laudo", "parecer"])


def needs_escalation_after_extract(dm) -> bool:
    page_evidence = _load_json_signal(dm, "page_evidence_v1") or []
    if not isinstance(page_evidence, list) or not page_evidence:
        return True

    anchors = []
    exact = 0
    patient_present = False
    provider_present = False

    for item in page_evidence:
        item_anchors = item.get("anchors") or []
        anchors.extend(item_anchors)
        exact += sum(1 for anchor in item_anchors if anchor.get("bbox"))
        people = item.get("people") or {}
        patient_present = patient_present or bool(people.get("patient_name"))
        provider_present = provider_present or bool(people.get("provider_name"))

    if not anchors:
        return True

    exact_rate = exact / max(len(anchors), 1)
    if exact_rate < 0.60:
        return True

    if _has_clinical_markers(dm) and not (patient_present or provider_present):
        return True

    return False


def build_processing_decision_details(sig, decision: ProcessingDecision) -> Dict[str, Any]:
    return {
        "mode": decision.mode,
        "reasons": list(decision.reasons),
        "confidence": decision.confidence,
        "signals": asdict(sig),
    }


def build_escalation_details(
    *,
    from_mode: ProcessingMode,
    to_mode: ProcessingMode,
    reason: str = "low_extract_quality_after_fast_path",
    warning_code: str = "pipeline_fallback_to_standard",
    degraded_mode: str = "standard_reprocess_after_fast_path",
) -> Dict[str, Any]:
    return {
        "from_mode": from_mode,
        "to_mode": to_mode,
        "reason": reason,
        "warning_code": warning_code,
        "degraded_mode": degraded_mode,
    }
