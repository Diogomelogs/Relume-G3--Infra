from __future__ import annotations

import json

from relluna.core.document_memory import (
    ArtefatoBruto,
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    Layer2Evidence,
    Layer3Evidence,
    MediaType,
    OriginType,
)
from relluna.core.document_memory.layer1 import ArtefatoTipo
from relluna.core.document_memory.layer3 import ProbatoryEvent
from relluna.core.document_memory.types_basic import ConfidenceState, EvidenceRef, ProvenancedString
from relluna.services.context_inference.basic import infer_layer3
from relluna.services.deterministic_extractors.timeline_seed_v2 import seed_timeline_v2
from relluna.services.derivatives.layer5 import apply_layer5
from relluna.services.entities.entities_canonical_v1 import apply_entities_canonical_v1
from relluna.services.read_model.timeline_builder import (
    build_document_timeline_read_model,
    build_timeline_consistency_warning,
)


def _timeline_policy_dm() -> DocumentMemory:
    citation = EvidenceRef(
        source_path="layer2.sinais_documentais.timeline_seed_v2",
        page=1,
        bbox=[10, 20, 30, 40],
        snippet="Data: 05/03/2024",
        confidence=0.95,
        provenance_status="exact",
        review_state="auto_confirmed",
    )
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="timeline-policy",
            contentfingerprint="2" * 64,
            ingestionagent="pytest",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="artifact-1",
                    tipo=ArtefatoTipo.original,
                    uri="memory://timeline-policy.pdf",
                    hash_sha256="2" * 64,
                )
            ],
        ),
        layer2=Layer2Evidence(),
        layer3=Layer3Evidence(
            eventos_probatorios=[
                ProbatoryEvent(
                    event_id="event-layer3-1",
                    event_type="document_issue_date",
                    title="Data de emissão",
                    description="Data documental observada no documento.",
                    date_iso="2024-03-05",
                    entities={"patient": "MARCOS ANTONIO REIS"},
                    citations=[citation],
                    confidence=0.95,
                    review_state="auto_confirmed",
                    provenance_status="exact",
                    derivation_rule="pytest",
                )
            ]
        ),
    )
    dm.layer2.sinais_documentais["timeline_seed_v2"] = ProvenancedString(
        valor=json.dumps(
            [
                {
                    "seed_id": "seed-1",
                    "date_iso": "2024-03-05",
                    "date_literal": "05/03/2024",
                    "event_hint": "document_issue_date",
                    "include_in_timeline": True,
                    "page": 1,
                    "bbox": [10, 20, 30, 40],
                    "snippet": "Data: 05/03/2024",
                    "source": "entities_canonical_v1",
                    "source_path": "layer2.sinais_documentais.entities_canonical_v1",
                    "confidence": 0.95,
                    "review_state": "auto_confirmed",
                    "provenance_status": "exact",
                }
            ],
            ensure_ascii=False,
        ),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )
    return dm


def _compound_subdocument_dm() -> DocumentMemory:
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="timeline-compound-subdocs",
            contentfingerprint="4" * 64,
            ingestionagent="pytest",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="artifact-2",
                    tipo=ArtefatoTipo.original,
                    uri="memory://timeline-compound-subdocs.pdf",
                    hash_sha256="4" * 64,
                )
            ],
        ),
        layer2=Layer2Evidence(),
        layer3=Layer3Evidence(),
    )
    page_evidence = [
        {
            "page": 1,
            "subdoc_id": "subdoc_001",
            "page_text": (
                "RECEITUARIO\n"
                "Paciente: CARLA FERNANDA NUNES\n"
                "Dr. LUIZ MORAES CRM 11111 SP\n"
                "Data: 10/01/2024\n"
            ),
            "page_taxonomy": {"value": "receituario"},
            "people": {
                "patient_name": "CARLA FERNANDA NUNES",
                "patient_confidence": 0.97,
                "patient_review_state": "auto_confirmed",
                "provider_name": "DR. LUIZ MORAES",
                "provider_confidence": 0.91,
                "provider_review_state": "review_recommended",
            },
            "administrative_entities": {"crm": ["CRM 11111 SP"]},
            "date_candidates": [{"literal": "10/01/2024", "date_iso": "2024-01-10"}],
            "anchors": [
                {
                    "label": "patient",
                    "value": "CARLA FERNANDA NUNES",
                    "snippet": "Paciente: CARLA FERNANDA NUNES",
                    "bbox": [10, 10, 220, 24],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "provider",
                    "value": "DR. LUIZ MORAES",
                    "snippet": "Dr. LUIZ MORAES CRM 11111 SP",
                    "bbox": [10, 30, 230, 44],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "date",
                    "value": "2024-01-10",
                    "snippet": "10/01/2024",
                    "bbox": [10, 50, 120, 64],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
            ],
            "signal_zones": [
                {
                    "label": "provider",
                    "value": "DR. LUIZ MORAES",
                    "page": 1,
                    "bbox": [10, 30, 230, 44],
                    "snippet": "Dr. LUIZ MORAES CRM 11111 SP",
                    "signal_zone": "core_probative",
                    "confidence": 0.95,
                    "review_state": "auto_confirmed",
                    "provenance_status": "exact",
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                }
            ],
            "clinical_entities": {"cids": []},
        },
        {
            "page": 2,
            "subdoc_id": "subdoc_002",
            "page_text": (
                "PARECER MEDICO\n"
                "Paciente: CARLA FERNANDA NUNES\n"
                "CID M51.1\n"
                "Dr. MAURO PINTO CRM 77881 SP\n"
                "Campinas, 18/05/2024\n"
            ),
            "page_taxonomy": {"value": "parecer_medico"},
            "people": {
                "patient_name": "CARLA FERNANDA NUNES",
                "patient_confidence": 0.95,
                "patient_review_state": "auto_confirmed",
                "provider_name": "DR. MAURO PINTO",
                "provider_confidence": 0.93,
                "provider_review_state": "review_recommended",
            },
            "administrative_entities": {"crm": ["CRM 77881 SP"]},
            "date_candidates": [{"literal": "18/05/2024", "date_iso": "2024-05-18"}],
            "anchors": [
                {
                    "label": "patient",
                    "value": "CARLA FERNANDA NUNES",
                    "snippet": "Paciente: CARLA FERNANDA NUNES",
                    "bbox": [10, 10, 220, 24],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "provider",
                    "value": "DR. MAURO PINTO",
                    "snippet": "Dr. MAURO PINTO CRM 77881 SP",
                    "bbox": [10, 50, 240, 64],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "cid",
                    "value": "M51.1",
                    "snippet": "CID M51.1",
                    "bbox": [10, 30, 90, 44],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "date",
                    "value": "2024-05-18",
                    "snippet": "18/05/2024",
                    "bbox": [10, 70, 120, 84],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
            ],
            "signal_zones": [
                {
                    "label": "cid",
                    "value": "M51.1",
                    "page": 2,
                    "bbox": [10, 30, 90, 44],
                    "snippet": "CID M51.1",
                    "signal_zone": "core_probative",
                    "confidence": 0.96,
                    "review_state": "auto_confirmed",
                    "provenance_status": "exact",
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                }
            ],
            "clinical_entities": {"cids": ["M51.1"]},
        },
    ]
    dm.layer2.sinais_documentais["page_evidence_v1"] = ProvenancedString(
        valor=json.dumps(page_evidence, ensure_ascii=False),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )
    dm.layer2.texto_ocr_literal = ProvenancedString(
        valor="\n\n".join(item["page_text"] for item in page_evidence),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )
    return dm


def test_timeline_policy_public_read_model_uses_layer3_probatory_events():
    public_timeline = build_document_timeline_read_model(_timeline_policy_dm())

    assert public_timeline["schema"] == "relluna.read_model.timeline.document.v2"
    assert public_timeline["summary"]["total_events"] == 1
    assert public_timeline["summary"]["needs_review_count"] == 0
    assert public_timeline["summary"]["anchored_events"] == 1
    assert public_timeline["summary"]["timeline_consistency_score"] == 100.0
    assert public_timeline["summary"]["warnings"] == []
    assert public_timeline["document"]["artifact_uri"] == "memory://timeline-policy.pdf"
    assert public_timeline["timeline"][0]["event_id"] == "event-layer3-1"
    assert public_timeline["timeline"][0]["date"] == "2024-03-05"
    assert public_timeline["timeline"][0]["title"] == "Data de emissão"
    assert public_timeline["timeline"][0]["description"] == "Data documental observada no documento."
    assert public_timeline["timeline"][0]["confidence"] == 0.95
    assert public_timeline["timeline"][0]["review_state"] == "auto_confirmed"
    assert public_timeline["timeline"][0]["provenance_status"] == "exact"
    assert public_timeline["timeline"][0]["entities"] == {"patient": "MARCOS ANTONIO REIS"}
    assert public_timeline["timeline"][0]["artifact_uri"] == "memory://timeline-policy.pdf"
    assert public_timeline["timeline"][0]["evidence_navigation"]["document_id"] == "timeline-policy"
    assert public_timeline["timeline"][0]["evidence_navigation"]["artifact_uri"] == "memory://timeline-policy.pdf"
    assert public_timeline["timeline"][0]["evidence_ref"]["bbox"] == [10, 20, 30, 40]
    assert public_timeline["timeline"][0]["evidence_ref"]["provenance_status"] == "exact"
    assert public_timeline["timeline"][0]["citations"][0]["provenance_status"] == "exact"


def test_timeline_policy_falls_back_to_timeline_seed_v2_for_legacy_documents():
    dm = _timeline_policy_dm()
    dm.layer3.eventos_probatorios = []

    public_timeline = build_document_timeline_read_model(dm)

    assert public_timeline["schema"] == "relluna.read_model.timeline.document.v2"
    assert public_timeline["summary"]["total_events"] == 1
    assert public_timeline["summary"]["needs_review_count"] == 0
    assert public_timeline["timeline"][0]["event_id"] == "seed-1"
    assert public_timeline["timeline"][0]["date"] == "2024-03-05"
    assert public_timeline["timeline"][0]["event_type"] == "document_issue_date"
    assert public_timeline["timeline"][0]["review_state"] == "auto_confirmed"
    assert public_timeline["timeline"][0]["provenance_status"] == "exact"
    assert public_timeline["timeline"][0]["artifact_uri"] == "memory://timeline-policy.pdf"
    assert public_timeline["timeline"][0]["evidence_navigation"]["document_id"] == "timeline-policy"
    assert public_timeline["timeline"][0]["evidence_ref"]["bbox"] == [10, 20, 30, 40]


def test_timeline_policy_layer5_future_source_uses_layer3_probatory_events():
    dm = apply_layer5(_timeline_policy_dm())
    layer5_timeline = dm.layer5.read_models["timeline_v1"]

    assert layer5_timeline["version"] == "layer5_read_model_v3"
    assert layer5_timeline["total_events"] == 1
    assert layer5_timeline["events"][0]["event_id"] == "event-layer3-1"
    assert layer5_timeline["events"][0]["event_type"] == "document_issue_date"
    assert layer5_timeline["events"][0]["date_iso"] == "2024-03-05"
    assert layer5_timeline["events"][0]["citations"][0]["bbox"] == [10, 20, 30, 40]


def test_timeline_policy_layer5_falls_back_to_seed_for_legacy_documents():
    dm = _timeline_policy_dm()
    dm.layer3.eventos_probatorios = []

    layer5_timeline = apply_layer5(dm).layer5.read_models["timeline_v1"]

    assert layer5_timeline["total_events"] == 1
    assert layer5_timeline["events"][0]["event_id"] == "seed-1"
    assert layer5_timeline["events"][0]["event_type"] == "document_issue_date"
    assert layer5_timeline["events"][0]["date_iso"] == "2024-03-05"
    assert layer5_timeline["events"][0]["provenance_status"] == "exact"
    assert layer5_timeline["events"][0]["citations"] == []


def test_timeline_policy_compatibility_bridge_must_not_diverge_on_count_or_date():
    dm = _timeline_policy_dm()
    public_timeline = build_document_timeline_read_model(dm)
    layer5_timeline = apply_layer5(dm).layer5.read_models["timeline_v1"]

    public_dates = [event["date"] for event in public_timeline["timeline"]]
    layer3_dates = [event["date_iso"] for event in layer5_timeline["events"]]

    assert public_timeline["summary"]["total_events"] == layer5_timeline["total_events"]
    assert public_dates == layer3_dates


def test_timeline_policy_compatibility_bridge_stays_aligned_for_legacy_seed_fallback():
    dm = _timeline_policy_dm()
    dm.layer3.eventos_probatorios = []

    public_timeline = build_document_timeline_read_model(dm)
    layer5_timeline = apply_layer5(dm).layer5.read_models["timeline_v1"]

    public_dates = [event["date"] for event in public_timeline["timeline"]]
    layer5_dates = [event["date_iso"] for event in layer5_timeline["events"]]

    assert public_timeline["summary"]["total_events"] == layer5_timeline["total_events"]
    assert public_dates == layer5_dates


def test_timeline_policy_public_payload_preserves_review_and_provenance_fields():
    dm = _timeline_policy_dm()
    dm.layer3.eventos_probatorios[0].review_state = "review_recommended"
    dm.layer3.eventos_probatorios[0].provenance_status = "inferred"
    dm.layer3.eventos_probatorios[0].confidence = 0.86

    public_timeline = build_document_timeline_read_model(dm)

    assert public_timeline["summary"]["needs_review_count"] == 1
    assert public_timeline["timeline"][0]["review_state"] == "review_recommended"
    assert public_timeline["timeline"][0]["provenance_status"] == "inferred"
    assert public_timeline["timeline"][0]["confidence"] == 0.86


def test_timeline_policy_emits_structured_warning_on_seed_layer3_divergence():
    dm = _timeline_policy_dm()
    dm.layer3.eventos_probatorios[0].date_iso = "2024-03-06"
    dm.layer3.eventos_probatorios.append(
        ProbatoryEvent(
            event_id="event-layer3-2",
            event_type="registro_condicao_clinica",
            title="Registro de condição clínica",
            date_iso="2024-03-07",
            confidence=0.86,
            review_state="review_recommended",
            provenance_status="inferred",
        )
    )

    warning = build_timeline_consistency_warning(dm)
    public_timeline = build_document_timeline_read_model(dm)
    layer5_timeline = apply_layer5(dm).layer5.read_models["timeline_v1"]

    assert warning["code"] == "timeline_seed_v2_layer3_divergence"
    assert warning["details"]["seed_event_count"] == 1
    assert warning["details"]["layer3_event_count"] == 2
    assert warning["details"]["seed_dates"] == ["2024-03-05"]
    assert warning["details"]["layer3_dates"] == ["2024-03-06", "2024-03-07"]
    assert warning["details"]["count_matches"] is False
    assert warning["details"]["dates_match"] is False

    assert public_timeline["summary"]["timeline_consistency_score"] == 0.0
    assert public_timeline["summary"]["warnings"] == [warning]
    assert public_timeline["warnings"] == [warning]
    assert layer5_timeline["timeline_consistency_score"] == 0.0
    assert layer5_timeline["warnings"] == [warning]


def test_public_timeline_prioritizes_subdocument_aware_events_for_compound_documents():
    dm = _compound_subdocument_dm()
    dm = apply_entities_canonical_v1(dm)
    dm = seed_timeline_v2(dm)
    dm = infer_layer3(dm)

    public_timeline = build_document_timeline_read_model(dm)

    assert public_timeline["summary"]["has_subdocuments"] is True
    assert public_timeline["summary"]["subdocument_count"] == 2
    assert public_timeline["summary"]["total_events"] == 3
    assert [event["subdoc_id"] for event in public_timeline["timeline"]] == [
        "subdoc_001",
        "subdoc_002",
        "subdoc_002",
    ]
    assert {(event["event_type"], event["date"], event["subdoc_id"]) for event in public_timeline["timeline"]} == {
        ("document_issue_date", "2024-01-10", "subdoc_001"),
        ("parecer_emitido", "2024-05-18", "subdoc_002"),
        ("registro_condicao_clinica", "2024-05-18", "subdoc_002"),
    }
    assert public_timeline["timeline"][0]["entities"]["provider"] == "DR. LUIZ MORAES"
    assert public_timeline["timeline"][1]["entities"]["provider"] == "DR. MAURO PINTO"
    assert public_timeline["timeline"][2]["entities"]["cids"] == ["M51.1"]
    assert public_timeline["timeline"][0]["evidence_navigation"]["subdoc_id"] == "subdoc_001"
    assert public_timeline["timeline"][1]["evidence_navigation"]["subdoc_id"] == "subdoc_002"
    assert public_timeline["timeline"][2]["evidence_ref"]["subdoc_id"] == "subdoc_002"

    compatibility_warning = next(
        warning
        for warning in public_timeline["warnings"]
        if warning["code"] == "entities_canonical_v1_global_is_compatibility_aggregate"
    )
    assert compatibility_warning["details"]["subdocument_count"] == 2
    assert (
        compatibility_warning["details"]["aggregate_projection_v1"]["authoritative_source"]
        == "subdocuments"
    )
