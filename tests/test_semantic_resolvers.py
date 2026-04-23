from __future__ import annotations

import json
from datetime import datetime, timezone

from relluna.core.document_memory import (
    ArtefatoBruto,
    DocumentMemory,
    Layer1Artefatos,
    MediaType,
    OriginType,
)
from relluna.core.document_memory.layer0 import Layer0Custodia
from relluna.core.document_memory.layer2 import Layer2Evidence
from relluna.core.document_memory.types_basic import ConfidenceState, ProvenancedString
from relluna.services.context_inference.basic import infer_layer3
from relluna.services.deterministic_extractors.timeline_seed_v2 import seed_timeline_v2
from relluna.services.entities.document_date_resolver import DocumentDateResolver
from relluna.services.entities.entities_canonical_v1 import apply_entities_canonical_v1
from relluna.services.entities.people_resolver import PeopleResolver
from relluna.services.page_extraction.page_pipeline import apply_page_analysis


def _page_evidence() -> list[dict]:
    return [
        {
            "page": 1,
            "page_text": (
                "Paciente: MARCOS ANTONIO REIS\n"
                "Mãe: ELIANE REIS\n"
                "Prestador: MARCOS ANTONIO REIS\n"
                "Data de nascimento: 20/01/1980\n"
                "Data: 05/03/2024\n"
                "CID S83.2\n"
            ),
            "page_taxonomy": {"value": "laudo_medico"},
            "people": {
                "patient_name": "MARCOS ANTONIO REIS",
                "patient_confidence": 0.95,
                "mother_name": "ELIANE REIS",
                "mother_confidence": 0.94,
                "provider_name": "MARCOS ANTONIO REIS",
                "provider_confidence": 0.95,
            },
            "date_candidates": [
                {"literal": "20/01/1980", "date_iso": "1980-01-20"},
                {"literal": "05/03/2024", "date_iso": "2024-03-05"},
            ],
            "anchors": [
                {
                    "label": "patient",
                    "snippet": "Paciente: MARCOS ANTONIO REIS",
                    "bbox": [10, 10, 200, 20],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "mother",
                    "snippet": "Mãe: ELIANE REIS",
                    "bbox": [10, 30, 200, 40],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "provider",
                    "snippet": "Prestador: MARCOS ANTONIO REIS",
                    "bbox": [10, 50, 200, 60],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "date",
                    "value": "1980-01-20",
                    "snippet": "Data de nascimento: 20/01/1980",
                    "bbox": [10, 70, 200, 80],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "date",
                    "value": "2024-03-05",
                    "snippet": "Data: 05/03/2024",
                    "bbox": [10, 90, 200, 100],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
            ],
            "clinical_entities": {"cids": ["S83.2"]},
        },
        {
            "page": 2,
            "page_text": "Prestador: ANA CAROLINA LIMA CRM 12345 SP",
            "page_taxonomy": {"value": "laudo_medico"},
            "people": {
                "provider_name": "ANA CAROLINA LIMA",
                "provider_confidence": 0.90,
            },
            "administrative_entities": {"crm": ["CRM 12345 SP"]},
            "anchors": [
                {
                    "label": "provider",
                    "snippet": "Prestador: ANA CAROLINA LIMA CRM 12345 SP",
                    "bbox": [10, 10, 260, 20],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
            ],
        },
    ]


def _dm_with_page_evidence(page_evidence: list[dict]) -> DocumentMemory:
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="semantic-resolver-test",
            contentfingerprint="2" * 64,
            ingestiontimestamp=datetime.now(timezone.utc),
            ingestionagent="pytest",
        ),
        layer2=Layer2Evidence(),
    )
    dm.layer2.sinais_documentais["page_evidence_v1"] = ProvenancedString(
        valor=json.dumps(page_evidence, ensure_ascii=False),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )
    return dm


def _document_dm_with_page_evidence(page_evidence: list[dict], ocr_text: str) -> DocumentMemory:
    dm = _dm_with_page_evidence(page_evidence)
    dm.layer1 = Layer1Artefatos(
        midia=MediaType.documento,
        origem=OriginType.digital_nativo,
        artefatos=[
            ArtefatoBruto(
                id="a1",
                tipo="original",
                uri="/tmp/semantic-subdoc.pdf",
                metadados_nativos={},
                logs_ingestao=[],
            )
        ],
    )
    dm.layer2.texto_ocr_literal = ProvenancedString(
        valor=ocr_text,
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )
    return dm


def _dm_with_layout_spans(spans: list[dict]) -> DocumentMemory:
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="semantic-resolver-layout-test",
            contentfingerprint="3" * 64,
            ingestiontimestamp=datetime.now(timezone.utc),
            ingestionagent="pytest",
        ),
        layer2=Layer2Evidence(),
    )
    dm.layer2.sinais_documentais["layout_spans_v1"] = ProvenancedString(
        valor=json.dumps(spans, ensure_ascii=False),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )
    return dm


def test_document_date_resolver_does_not_promote_birth_date():
    result = DocumentDateResolver().resolve(_page_evidence())

    assert result["date_iso"] == "2024-03-05"
    assert result["confidence"] > 0
    assert result["reason"]
    assert result["evidence_refs"]
    assert "nascimento" not in result["evidence_refs"][0]["snippet"].lower()


def test_people_resolver_keeps_patient_provider_and_mother_distinct():
    result = PeopleResolver().resolve(_page_evidence())

    assert result["patient"]["name"] == "MARCOS ANTONIO REIS"
    assert result["provider"]["name"] == "ANA CAROLINA LIMA"
    assert result["mother"]["name"] == "ELIANE REIS"
    assert result["patient"]["name"] != result["provider"]["name"]
    assert result["mother"]["name"] != result["patient"]["name"]
    assert result["provider"]["confidence"] > 0
    assert result["provider"]["reason"]
    assert result["provider"]["evidence_refs"]


def test_entities_canonical_uses_structured_semantic_resolutions():
    dm = apply_entities_canonical_v1(_dm_with_page_evidence(_page_evidence()))
    canonical = json.loads(dm.layer2.sinais_documentais["entities_canonical_v1"].valor)

    assert canonical["document_date"]["date_iso"] == "2024-03-05"
    assert canonical["patient"]["name"] != canonical["provider"]["name"]
    assert canonical["mother"]["name"] != canonical["patient"]["name"]
    assert canonical["semantic_resolution_v1"]["document_date"]["evidence_refs"]
    assert canonical["semantic_resolution_v1"]["people"]["provider"]["reason"]


def test_entities_timeline_and_layer3_preserve_subdocument_isolation():
    page_evidence = [
        {
            "page": 1,
            "subdoc_id": "subdoc_001",
            "page_text": (
                "Paciente: CARLA FERNANDA NUNES\n"
                "Data: 10/01/2024\n"
                "RECEITUARIO\n"
            ),
            "page_taxonomy": {"value": "receituario"},
            "people": {
                "patient_name": "CARLA FERNANDA NUNES",
                "patient_confidence": 0.96,
                "patient_review_state": "auto_confirmed",
            },
            "date_candidates": [
                {"literal": "10/01/2024", "date_iso": "2024-01-10"},
            ],
            "anchors": [
                {
                    "label": "patient",
                    "value": "CARLA FERNANDA NUNES",
                    "snippet": "Paciente: CARLA FERNANDA NUNES",
                    "bbox": [10, 10, 220, 24],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "date",
                    "value": "2024-01-10",
                    "snippet": "10/01/2024",
                    "bbox": [10, 30, 120, 44],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
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
            "date_candidates": [
                {"literal": "18/05/2024", "date_iso": "2024-05-18"},
            ],
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
            "clinical_entities": {"cids": ["M51.1"]},
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
        },
    ]
    ocr_text = "\n\n".join(item["page_text"] for item in page_evidence)
    dm = _document_dm_with_page_evidence(page_evidence, ocr_text)

    dm = apply_entities_canonical_v1(dm)
    canonical = json.loads(dm.layer2.sinais_documentais["entities_canonical_v1"].valor)

    assert canonical["document_type"] == "parecer_medico"
    assert canonical["document_date"]["date_iso"] == "2024-01-10"
    assert [subdoc["subdoc_id"] for subdoc in canonical["subdocuments"]] == [
        "subdoc_001",
        "subdoc_002",
    ]
    assert canonical["subdocuments"][0]["document_type"] == "receituario"
    assert canonical["subdocuments"][0]["document_date"]["date_iso"] == "2024-01-10"
    assert canonical["subdocuments"][1]["document_type"] == "parecer_medico"
    assert canonical["subdocuments"][1]["document_date"]["date_iso"] == "2024-05-18"
    assert canonical["subdocuments"][1]["provider"]["name"] == "DR. MAURO PINTO"

    dm = seed_timeline_v2(dm)
    seeds = json.loads(dm.layer2.sinais_documentais["timeline_seed_v2"].valor)

    assert {(seed["subdoc_id"], seed["event_hint"], seed["date_iso"]) for seed in seeds} == {
        ("subdoc_001", "document_issue_date", "2024-01-10"),
        ("subdoc_002", "parecer_emitido", "2024-05-18"),
        ("subdoc_002", "registro_condicao_clinica", "2024-05-18"),
    }

    dm = infer_layer3(dm)
    events = dm.layer3.eventos_probatorios

    assert {(event.subdoc_id, event.event_type, event.date_iso) for event in events} == {
        ("subdoc_001", "document_issue_date", "2024-01-10"),
        ("subdoc_002", "parecer_emitido", "2024-05-18"),
        ("subdoc_002", "registro_condicao_clinica", "2024-05-18"),
    }
    assert all(event.citations[0].subdoc_id == event.subdoc_id for event in events)


def test_page_analysis_resolves_patient_from_generic_nome_header():
    spans = [
        {"page": 1, "text": "Nome: MARIA SILVA", "bbox": [10, 10, 120, 20]},
        {"page": 1, "text": "Nome da mãe: JOSEFA SILVA", "bbox": [10, 30, 180, 40]},
        {"page": 1, "text": "Prestador: DRA ANA LIMA", "bbox": [10, 50, 180, 60]},
        {"page": 1, "text": "CRM 12345 SP", "bbox": [10, 70, 100, 80]},
        {"page": 1, "text": "Data de nascimento: 20/01/1980", "bbox": [10, 90, 200, 100]},
        {"page": 1, "text": "Data: 05/03/2024", "bbox": [10, 110, 120, 120]},
    ]

    dm = apply_page_analysis(_dm_with_layout_spans(spans))
    page_evidence = json.loads(dm.layer2.sinais_documentais["page_evidence_v1"].valor)
    page = page_evidence[0]

    assert page["people"]["patient_name"] == "MARIA SILVA"
    assert page["people"]["patient_confidence"] == 0.98
    assert page["people"]["patient_review_state"] == "auto_confirmed"
    patient_anchors = [anchor for anchor in page["anchors"] if anchor["label"] == "patient"]
    assert len(patient_anchors) == 1
    patient_anchor = patient_anchors[0]
    assert patient_anchor["snippet"] == "Paciente: MARIA SILVA"
    assert patient_anchor["bbox"] == [10.0, 10.0, 120.0, 20.0]
    assert patient_anchor["review_state"] == "auto_confirmed"
    assert patient_anchor["provenance_status"] == "exact"


def test_people_resolver_and_canonical_keep_two_token_patient_with_strong_anchor():
    page_evidence = [
        {
            "page": 1,
            "page_text": (
                "Nome: MARIA SILVA\n"
                "Nome da mãe: JOSEFA SILVA\n"
                "Prestador: DRA ANA LIMA CRM 12345 SP\n"
                "Data de nascimento: 20/01/1980\n"
                "Data: 05/03/2024\n"
            ),
            "page_taxonomy": {"value": "laudo_medico"},
            "people": {
                "patient_name": "MARIA SILVA",
                "patient_confidence": 0.98,
                "patient_review_state": "auto_confirmed",
                "mother_name": "JOSEFA SILVA",
                "mother_confidence": 0.94,
                "mother_review_state": "review_recommended",
                "provider_name": "DRA ANA LIMA",
                "provider_confidence": 0.94,
                "provider_review_state": "review_recommended",
            },
            "administrative_entities": {"crm": ["CRM 12345 SP"]},
            "date_candidates": [
                {"literal": "20/01/1980", "date_iso": "1980-01-20"},
                {"literal": "05/03/2024", "date_iso": "2024-03-05"},
            ],
            "anchors": [
                {
                    "label": "patient",
                    "snippet": "Nome: MARIA SILVA",
                    "bbox": [10, 10, 120, 20],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "mother",
                    "snippet": "Nome da mãe: JOSEFA SILVA",
                    "bbox": [10, 30, 180, 40],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "provider",
                    "snippet": "Prestador: DRA ANA LIMA CRM 12345 SP",
                    "bbox": [10, 50, 220, 60],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
            ],
        }
    ]

    resolved = PeopleResolver().resolve(page_evidence)
    assert resolved["patient"]["name"] == "MARIA SILVA"
    assert resolved["patient"]["review_state"] == "auto_confirmed"
    assert resolved["patient"]["evidence_refs"][0]["bbox"] == [10, 10, 120, 20]

    dm = apply_entities_canonical_v1(_dm_with_page_evidence(page_evidence))
    canonical = json.loads(dm.layer2.sinais_documentais["entities_canonical_v1"].valor)

    assert canonical["patient"]["name"] == "MARIA SILVA"
    assert canonical["patient"]["evidence"]["bbox"] == [10, 10, 120, 20]
    assert canonical["patient"]["review_state"] == "auto_confirmed"
    assert canonical["semantic_resolution_v1"]["people"]["patient"]["reason"] == "patient_anchor_candidate"
    assert "implausible_patient_name" not in canonical["quality"]["warnings"]


def test_people_resolver_and_canonical_keep_two_token_patient_with_page_text_header_without_bbox():
    page_evidence = [
        {
            "page": 1,
            "page_text": (
                "Nome: MARIA SILVA\n"
                "Nome da mãe: JOSEFA SILVA\n"
                "Prestador: DRA ANA LIMA CRM 12345 SP\n"
                "Data: 05/03/2024\n"
            ),
            "page_taxonomy": {"value": "laudo_medico"},
            "people": {
                "patient_name": "MARIA SILVA",
                "patient_confidence": 0.90,
                "patient_review_state": "review_recommended",
                "mother_name": "JOSEFA SILVA",
                "mother_confidence": 0.86,
                "mother_review_state": "review_recommended",
                "provider_name": "DRA ANA LIMA",
                "provider_confidence": 0.94,
                "provider_review_state": "review_recommended",
            },
            "administrative_entities": {"crm": ["CRM 12345 SP"]},
            "anchors": [
                {
                    "label": "patient",
                    "snippet": "Paciente: MARIA SILVA",
                    "bbox": None,
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "mother",
                    "snippet": "Mãe: JOSEFA SILVA",
                    "bbox": None,
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "provider",
                    "snippet": "Prestador: DRA ANA LIMA",
                    "bbox": None,
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
            ],
            "date_candidates": [
                {"literal": "05/03/2024", "date_iso": "2024-03-05"},
            ],
            "clinical_entities": {"cids": []},
        }
    ]

    resolved = PeopleResolver().resolve(page_evidence)
    assert resolved["patient"]["name"] == "MARIA SILVA"
    assert resolved["patient"]["review_state"] == "review_recommended"
    assert resolved["patient"]["evidence_refs"][0]["bbox"] is None
    assert resolved["patient"]["evidence_refs"][0]["provenance_status"] == "text_fallback"

    dm = apply_entities_canonical_v1(_dm_with_page_evidence(page_evidence))
    canonical = json.loads(dm.layer2.sinais_documentais["entities_canonical_v1"].valor)

    assert canonical["patient"]["name"] == "MARIA SILVA"
    assert canonical["patient"]["review_state"] == "review_recommended"
    assert canonical["patient"]["evidence"]["bbox"] is None
    assert canonical["patient"]["evidence"]["provenance_status"] == "text_fallback"


def test_page_analysis_and_canonical_resolve_explicit_patient_with_honorific_in_simple_pdf():
    spans = [
        {"page": 1, "text": "Paciente: Sr(a). MARIA SILVA", "bbox": [10, 10, 220, 20]},
        {"page": 1, "text": "Data: 05/03/2024", "bbox": [10, 30, 120, 40]},
    ]

    dm = apply_page_analysis(_dm_with_layout_spans(spans))
    page_evidence = json.loads(dm.layer2.sinais_documentais["page_evidence_v1"].valor)

    assert page_evidence[0]["people"]["patient_name"] == "MARIA SILVA"

    dm = apply_entities_canonical_v1(dm)
    canonical = json.loads(dm.layer2.sinais_documentais["entities_canonical_v1"].valor)

    assert canonical["patient"]["name"] == "MARIA SILVA"
    assert canonical["patient"]["evidence"]["bbox"] == [10.0, 10.0, 220.0, 20.0]


def test_people_resolver_prefers_distinct_provider_when_patient_name_matches_honorific_variant():
    page_evidence = [
        {
            "page": 1,
            "page_text": (
                "Paciente: ANA LIMA\n"
                "Prestador: DRA ANA LIMA CRM 12345 SP\n"
                "Data: 05/03/2024\n"
            ),
            "page_taxonomy": {"value": "laudo_medico"},
            "people": {
                "patient_name": "ANA LIMA",
                "patient_confidence": 0.95,
                "patient_review_state": "review_recommended",
                "provider_name": "DRA ANA LIMA",
                "provider_confidence": 0.95,
                "provider_review_state": "review_recommended",
            },
            "administrative_entities": {"crm": ["CRM 12345 SP"]},
            "anchors": [
                {
                    "label": "patient",
                    "snippet": "Paciente: ANA LIMA",
                    "bbox": None,
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "provider",
                    "snippet": "Prestador: DRA ANA LIMA CRM 12345 SP",
                    "bbox": None,
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
            ],
        },
        {
            "page": 2,
            "page_text": "Prestador: DR CARLOS SOUZA CRM 98765 SP",
            "page_taxonomy": {"value": "laudo_medico"},
            "people": {
                "provider_name": "DR CARLOS SOUZA",
                "provider_confidence": 0.93,
                "provider_review_state": "review_recommended",
            },
            "administrative_entities": {"crm": ["CRM 98765 SP"]},
            "anchors": [
                {
                    "label": "provider",
                    "snippet": "Prestador: DR CARLOS SOUZA CRM 98765 SP",
                    "bbox": [10, 10, 260, 20],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                }
            ],
        },
    ]

    resolved = PeopleResolver().resolve(page_evidence)

    assert resolved["patient"]["name"] == "ANA LIMA"
    assert resolved["provider"]["name"] == "DR CARLOS SOUZA"

    dm = apply_entities_canonical_v1(_dm_with_page_evidence(page_evidence))
    canonical = json.loads(dm.layer2.sinais_documentais["entities_canonical_v1"].valor)

    assert canonical["patient"]["name"] == "ANA LIMA"
    assert canonical["provider"]["name"] == "DR CARLOS SOUZA"


def test_people_resolver_and_canonical_keep_patient_and_mother_distinct_with_explicit_headers():
    page_evidence = [
        {
            "page": 1,
            "page_text": (
                "Nome do paciente: MARIA SILVA\n"
                "Nome da mãe: JOSEFA SILVA\n"
                "Data: 05/03/2024\n"
            ),
            "page_taxonomy": {"value": "laudo_medico"},
            "people": {
                "patient_name": "MARIA SILVA",
                "patient_confidence": 0.92,
                "patient_review_state": "review_recommended",
                "mother_name": "JOSEFA SILVA",
                "mother_confidence": 0.90,
                "mother_review_state": "review_recommended",
            },
            "anchors": [
                {
                    "label": "patient",
                    "snippet": "Nome do paciente: MARIA SILVA",
                    "bbox": None,
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "mother",
                    "snippet": "Nome da mãe: JOSEFA SILVA",
                    "bbox": None,
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
            ],
            "date_candidates": [{"literal": "05/03/2024", "date_iso": "2024-03-05"}],
            "clinical_entities": {"cids": []},
        }
    ]

    resolved = PeopleResolver().resolve(page_evidence)

    assert resolved["patient"]["name"] == "MARIA SILVA"
    assert resolved["mother"]["name"] == "JOSEFA SILVA"
    assert resolved["patient"]["name"] != resolved["mother"]["name"]

    dm = apply_entities_canonical_v1(_dm_with_page_evidence(page_evidence))
    canonical = json.loads(dm.layer2.sinais_documentais["entities_canonical_v1"].valor)

    assert canonical["patient"]["name"] == "MARIA SILVA"
    assert canonical["mother"]["name"] == "JOSEFA SILVA"
    assert canonical["patient"]["name"] != canonical["mother"]["name"]
