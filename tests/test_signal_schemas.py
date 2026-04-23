from __future__ import annotations

import json
from datetime import datetime, timezone

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.layer0 import Layer0Custodia
from relluna.core.document_memory.layer2 import Layer2Evidence
from relluna.core.document_memory.types_basic import ConfidenceState, ProvenancedString
from relluna.services.deterministic_extractors.timeline_seed_v2 import seed_timeline_v2
from relluna.services.evidence.signals import (
    WARNING_SIGNAL_KEY,
    dump_critical_signal_json,
    load_critical_signal_json,
)


def _dm() -> DocumentMemory:
    return DocumentMemory(
        layer0=Layer0Custodia(
            documentid="signal-schema-test",
            contentfingerprint="3" * 64,
            ingestiontimestamp=datetime.now(timezone.utc),
            ingestionagent="pytest",
        ),
        layer2=Layer2Evidence(),
    )


def _signal(value: str) -> ProvenancedString:
    return ProvenancedString(
        valor=value,
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )


def test_invalid_critical_signal_json_emits_structured_warning():
    dm = _dm()
    dm.layer2.sinais_documentais["entities_canonical_v1"] = _signal("{not-json")

    assert load_critical_signal_json(dm, "entities_canonical_v1") is None

    warnings = json.loads(dm.layer2.sinais_documentais[WARNING_SIGNAL_KEY].valor)
    assert warnings[0]["code"] == "critical_signal_invalid_json"
    assert warnings[0]["signal"] == "entities_canonical_v1"
    assert warnings[0]["schema_version"] == "entities_canonical_v1"


def test_schema_validation_warning_keeps_legacy_payload_as_fallback():
    dm = _dm()
    legacy_payload = [{"page_text": "sem page obrigatório, mas legado deve sobreviver"}]

    serialized = dump_critical_signal_json("page_evidence_v1", legacy_payload, dm=dm)

    assert json.loads(serialized) == legacy_payload
    warnings = json.loads(dm.layer2.sinais_documentais[WARNING_SIGNAL_KEY].valor)
    assert warnings[0]["code"] == "critical_signal_schema_validation_failed"
    assert warnings[0]["details"]["operation"] == "write"


def test_timeline_seed_v2_read_write_uses_schema_and_preserves_valid_payload():
    dm = _dm()
    dm.layer2.sinais_documentais["entities_canonical_v1"] = _signal(
        json.dumps(
            {
                "document_type": "laudo_medico",
                "provider": {"name": "ANA LIMA"},
                "document_date": {
                    "date_iso": "2024-03-05",
                    "literal": "05/03/2024",
                    "confidence": 0.97,
                    "evidence": {
                        "page": 1,
                        "bbox": [1, 2, 3, 4],
                        "snippet": "Data: 05/03/2024",
                        "source_path": "layer2.sinais_documentais.page_evidence_v1",
                    },
                },
                "clinical": {},
            },
            ensure_ascii=False,
        )
    )

    dm = seed_timeline_v2(dm)
    seeds = load_critical_signal_json(dm, "timeline_seed_v2")

    assert seeds[0]["date_iso"] == "2024-03-05"
    assert seeds[0]["event_hint"] == "document_issue_date"
    assert WARNING_SIGNAL_KEY not in dm.layer2.sinais_documentais


def test_epistemic_segmentation_signals_accept_minimal_valid_payloads():
    dm = _dm()

    page_units = dump_critical_signal_json(
        "page_unit_v1",
        [
            {
                "page_index": 1,
                "subdoc_id": "subdoc_001",
                "warnings": [],
                "uncertainties": ["patient_unknown"],
                "evidence_refs": [],
            }
        ],
        dm=dm,
    )
    subdocument_units = dump_critical_signal_json(
        "subdocument_unit_v1",
        [
            {
                "subdoc_id": "subdoc_001",
                "pages": [1],
                "warnings": [],
                "uncertainties": ["patient_unknown"],
                "evidence_refs": [],
            }
        ],
        dm=dm,
    )
    relation_graph = dump_critical_signal_json(
        "document_relation_graph_v1",
        {"nodes": [{"subdoc_id": "subdoc_001"}], "edges": [], "summary": {"edge_count": 0}},
        dm=dm,
    )

    assert json.loads(page_units)[0]["page_index"] == 1
    assert json.loads(subdocument_units)[0]["subdoc_id"] == "subdoc_001"
    assert json.loads(relation_graph)["summary"]["edge_count"] == 0
