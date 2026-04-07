from __future__ import annotations

import json
from typing import List

from relluna.core.document_memory import DocumentMemory
from relluna.domain.legal_fields import CanonicalExtraction
from relluna.services.legal.alert_engine import evaluate_alerts
from relluna.services.legal.fact_builder import build_facts


def _load_legal_extraction(dm: DocumentMemory) -> CanonicalExtraction | None:
    if dm.layer2 is None:
        return None
    sig = dm.layer2.sinais_documentais.get("legal_canonical_fields_v1")
    if not sig or not getattr(sig, "valor", None):
        return None
    try:
        return CanonicalExtraction.model_validate_json(sig.valor)
    except Exception:
        return None


def build_case_outputs(documents: List[DocumentMemory]) -> dict:
    extractions = []
    for dm in documents:
        ext = _load_legal_extraction(dm)
        if ext is not None:
            extractions.append(ext)

    facts = build_facts(extractions)
    alerts = evaluate_alerts(extractions)

    return {
        "canonical_extractions": [e.model_dump() for e in extractions],
        "timeline_facts": [f.model_dump() for f in facts],
        "legal_alerts": [a.model_dump() for a in alerts],
    }