from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, RootModel, TypeAdapter, ValidationError

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.types_basic import ProvenancedString
from relluna.domain.legal_fields import CanonicalExtraction

FONTE = "services.evidence.signals"
WARNING_SIGNAL_KEY = "signal_validation_warnings_v1"


class PageEvidenceItemV1(BaseModel):
    model_config = ConfigDict(extra="allow")

    page: int
    page_text: Optional[str] = None
    people: Dict[str, Any] = Field(default_factory=dict)
    date_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    anchors: List[Dict[str, Any]] = Field(default_factory=list)


class PageEvidenceV1Signal(RootModel[List[PageEvidenceItemV1]]):
    model_config = ConfigDict(title="page_evidence_v1")


class EntitiesCanonicalV1Signal(BaseModel):
    model_config = ConfigDict(extra="allow", title="entities_canonical_v1")

    document_type: Optional[str] = None
    patient: Optional[Dict[str, Any]] = None
    mother: Optional[Dict[str, Any]] = None
    provider: Optional[Dict[str, Any]] = None
    clinical: Dict[str, Any] = Field(default_factory=dict)
    document_date: Optional[Dict[str, Any]] = None


class TimelineSeedV2Item(BaseModel):
    model_config = ConfigDict(extra="allow")

    seed_id: str
    date_iso: str
    event_hint: str
    include_in_timeline: bool = False
    confidence: float
    source: str
    source_path: str


class TimelineSeedV2Signal(RootModel[List[TimelineSeedV2Item]]):
    model_config = ConfigDict(title="timeline_seed_v2")


class PageUnitV1Item(BaseModel):
    model_config = ConfigDict(extra="allow")

    page_index: int
    subdoc_id: Optional[str] = None
    evidence_refs: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)


class PageUnitV1Signal(RootModel[List[PageUnitV1Item]]):
    model_config = ConfigDict(title="page_unit_v1")


class SubdocumentUnitV1Item(BaseModel):
    model_config = ConfigDict(extra="allow")

    subdoc_id: str
    pages: List[int] = Field(default_factory=list)
    evidence_refs: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)


class SubdocumentUnitV1Signal(RootModel[List[SubdocumentUnitV1Item]]):
    model_config = ConfigDict(title="subdocument_unit_v1")


class DocumentRelationGraphV1Signal(BaseModel):
    model_config = ConfigDict(extra="allow", title="document_relation_graph_v1")

    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)


_ADAPTERS: Dict[str, TypeAdapter[Any]] = {
    "page_evidence_v1": TypeAdapter(PageEvidenceV1Signal),
    "page_unit_v1": TypeAdapter(PageUnitV1Signal),
    "subdocument_unit_v1": TypeAdapter(SubdocumentUnitV1Signal),
    "document_relation_graph_v1": TypeAdapter(DocumentRelationGraphV1Signal),
    "entities_canonical_v1": TypeAdapter(EntitiesCanonicalV1Signal),
    "timeline_seed_v2": TypeAdapter(TimelineSeedV2Signal),
    "legal_canonical_fields_v1": TypeAdapter(CanonicalExtraction),
}


def _warning_payload(key: str, code: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "code": code,
        "severity": "warning",
        "source": FONTE,
        "signal": key,
        "schema_version": key,
        "message": message,
        "details": details or {},
    }


def _append_validation_warning(dm: Optional[DocumentMemory], warning: Dict[str, Any]) -> None:
    if dm is None or dm.layer2 is None:
        return

    current: List[Dict[str, Any]] = []
    sig = dm.layer2.sinais_documentais.get(WARNING_SIGNAL_KEY)
    if sig and getattr(sig, "valor", None):
        try:
            loaded = json.loads(sig.valor)
            if isinstance(loaded, list):
                current = [item for item in loaded if isinstance(item, dict)]
        except Exception:
            current = []

    if warning not in current:
        current.append(warning)

    dm.layer2.sinais_documentais[WARNING_SIGNAL_KEY] = ProvenancedString(
        valor=json.dumps(current, ensure_ascii=False, default=str),
        fonte=FONTE,
        metodo="critical_signal_validation_warning",
        estado="confirmado",
        confianca=1.0,
    )


def validate_critical_signal_payload(
    key: str,
    payload: Any,
    *,
    dm: Optional[DocumentMemory] = None,
    operation: str = "read",
) -> Any:
    adapter = _ADAPTERS.get(key)
    if adapter is None:
        return payload

    try:
        adapter.validate_python(payload)
    except ValidationError as exc:
        _append_validation_warning(
            dm,
            _warning_payload(
                key,
                "critical_signal_schema_validation_failed",
                "Sinal crítico não aderiu completamente ao schema; usando fallback compatível.",
                {
                    "operation": operation,
                    "error_count": len(exc.errors()),
                    "first_error": exc.errors()[0] if exc.errors() else None,
                },
            ),
        )
    return payload


def dump_critical_signal_json(key: str, payload: Any, *, dm: Optional[DocumentMemory] = None) -> str:
    validated = validate_critical_signal_payload(key, payload, dm=dm, operation="write")
    return json.dumps(validated, ensure_ascii=False, default=str)


def load_critical_signal_json(dm: DocumentMemory, key: str) -> Any:
    if dm.layer2 is None:
        return None
    sig = dm.layer2.sinais_documentais.get(key)
    if not sig or not getattr(sig, "valor", None):
        return None

    try:
        payload = json.loads(sig.valor)
    except Exception as exc:
        _append_validation_warning(
            dm,
            _warning_payload(
                key,
                "critical_signal_invalid_json",
                "Sinal crítico contém JSON inválido; usando fallback vazio compatível.",
                {"error_type": exc.__class__.__name__, "message": str(exc) or exc.__class__.__name__},
            ),
        )
        return None

    return validate_critical_signal_payload(key, payload, dm=dm, operation="read")
