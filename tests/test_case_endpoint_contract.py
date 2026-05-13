from __future__ import annotations

import json
import asyncio
from datetime import datetime, timezone

from relluna.core.document_memory import (
    ArtefatoBruto,
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    Layer2Evidence,
    OriginType,
    ProvenancedString,
)
from relluna.core.document_memory.layer1 import ArtefatoTipo
from relluna.core.document_memory.layer1 import MediaType
from relluna.core.document_memory.layer3 import ProbatoryEvent
from relluna.core.document_memory.types_basic import ConfidenceState, EvidenceRef, InferredString
from relluna.services.ingestion.api import get_document_case
from relluna.services.read_model.case_builder import build_document_case_read_model
from tests.fakes import fake_mongo_store


def _signal(value):
    return ProvenancedString(
        valor=json.dumps(value, ensure_ascii=False),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )


def _case_dm() -> DocumentMemory:
    return DocumentMemory(
        layer0=Layer0Custodia(
            documentid="case-doc-1",
            contentfingerprint="c" * 64,
            ingestiontimestamp=datetime.now(timezone.utc),
            ingestionagent="pytest",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="artifact-1",
                    tipo=ArtefatoTipo.original,
                    uri="memory://case-doc-1.pdf",
                )
            ],
        ),
        layer2=Layer2Evidence(
            sinais_documentais={
                "entities_canonical_v1": _signal(
                    {
                        "document_type": "atestado_medico",
                        "patient": {
                            "name": "MARIA SILVA",
                            "confidence": 0.98,
                            "review_state": "auto_confirmed",
                            "evidence": {
                                "page": 1,
                                "bbox": [10, 10, 120, 20],
                                "snippet": "Paciente: MARIA SILVA",
                                "source_path": "layer2.sinais_documentais.page_evidence_v1",
                                "provenance_status": "exact",
                            },
                        },
                        "provider": {
                            "name": "DRA ANA LIMA",
                            "crm": "12345",
                            "confidence": 0.93,
                            "review_state": "review_recommended",
                            "evidence": {
                                "page": 1,
                                "bbox": None,
                                "snippet": "Dra Ana Lima CRM 12345",
                                "source_path": "layer2.sinais_documentais.page_evidence_v1",
                                "provenance_status": "snippet_only",
                            },
                        },
                        "document_date": {
                            "date_iso": "2024-03-05",
                            "literal": "05/03/2024",
                            "confidence": 0.97,
                            "review_state": "auto_confirmed",
                            "evidence": {
                                "page": 1,
                                "bbox": [150, 10, 210, 20],
                                "snippet": "Data: 05/03/2024",
                                "source_path": "layer2.sinais_documentais.page_evidence_v1",
                                "provenance_status": "exact",
                            },
                        },
                        "clinical": {
                            "cids": [
                                {
                                    "code": "M54.5",
                                    "confidence": 0.96,
                                    "evidence": {
                                        "page": 1,
                                        "bbox": [220, 10, 280, 20],
                                        "snippet": "CID M54.5",
                                        "source_path": "layer2.sinais_documentais.page_evidence_v1",
                                        "provenance_status": "exact",
                                    },
                                }
                            ]
                        },
                        "afastamento": {
                            "estimated_end": {
                                "date_iso": "2024-03-10",
                                "confidence": 0.8,
                                "evidence": {
                                    "page": 1,
                                    "bbox": None,
                                    "snippet": "Afastado por 5 dia(s)",
                                    "source_path": "layer2.texto_ocr_literal.valor",
                                    "provenance_status": "inferred",
                                },
                            }
                        },
                        "quality": {"warnings": ["provider_without_exact_bbox"]},
                    }
                ),
                "legal_canonical_fields_v1": _signal(
                    {
                        "document_id": "case-doc-1",
                        "doc_type": "atestado_medico",
                        "confidence": 0.98,
                        "schema_version": "legal_canonical_fields_v1",
                        "source_signal": "entities_canonical_v1",
                        "source_path": "layer2.sinais_documentais.entities_canonical_v1",
                        "warnings": ["provider_without_exact_bbox"],
                        "fields": [
                            {
                                "name": "Nome_Paciente",
                                "value": "MARIA SILVA",
                                "normalized_value": "MARIA SILVA",
                                "confidence": 0.98,
                                "source_doc_type": "atestado_medico",
                                "anchor": {"page": 1, "bbox": [10, 10, 120, 20], "snippet": "Paciente: MARIA SILVA"},
                                "assertion_level": "observed",
                                "provenance_status": "exact",
                                "review_state": "auto_confirmed",
                                "source_signal": "entities_canonical_v1",
                                "source_path": "layer2.sinais_documentais.page_evidence_v1",
                                "evidence_refs": [
                                    {
                                        "page": 1,
                                        "bbox": [10, 10, 120, 20],
                                        "snippet": "Paciente: MARIA SILVA",
                                        "source_path": "layer2.sinais_documentais.page_evidence_v1",
                                        "provenance_status": "exact",
                                    }
                                ],
                            }
                        ],
                    }
                ),
                "timeline_seed_v2": _signal(
                    [
                        {
                            "seed_id": "seed-1",
                            "date_iso": "2024-03-05",
                            "date_literal": "05/03/2024",
                            "event_hint": "document_issue_date",
                            "include_in_timeline": True,
                            "confidence": 0.97,
                            "source": "timeline_seed_v2",
                            "source_path": "layer2.sinais_documentais.timeline_seed_v2[0]",
                            "page": 1,
                            "bbox": [150, 10, 210, 20],
                            "snippet": "Data: 05/03/2024",
                            "provenance_status": "exact",
                            "review_state": "auto_confirmed",
                        }
                    ]
                ),
            }
        ),
        layer3={
            "tipo_documento": InferredString(valor="atestado_medico"),
            "eventos_probatorios": [
                ProbatoryEvent(
                    event_id="event-1",
                    event_type="document_issue_date",
                    title="Data de emissão",
                    description="Data documental observada no documento.",
                    date_iso="2024-03-05",
                    confidence=0.97,
                    review_state="auto_confirmed",
                    provenance_status="exact",
                    entities={"patient": "MARIA SILVA", "provider": "DRA ANA LIMA", "cids": ["M54.5"]},
                    citations=[
                        EvidenceRef(
                            source_path="layer2.sinais_documentais.page_evidence_v1",
                            page=1,
                            bbox=[150, 10, 210, 20],
                            snippet="Data: 05/03/2024",
                            confidence=0.97,
                            provenance_status="exact",
                            review_state="auto_confirmed",
                        )
                    ],
                )
            ],
        },
        layer4={
            "data_canonica": "2024-03-05",
            "periodo": "2024-03",
            "tags": ["saude", "afastamento"],
            "entidades": [{"kind": "patient", "label": "MARIA SILVA"}],
        },
    )


def test_case_builder_contract_reuses_public_and_derived_views():
    case = build_document_case_read_model(_case_dm())

    assert case["schema"] == "relluna.read_model.case.document.v1"
    assert case["document"]["document_id"] == "case-doc-1"
    assert case["document"]["artifact_uri"] == "memory://case-doc-1.pdf"
    assert case["summary"]["total_timeline_events"] == 1
    assert case["summary"]["timeline_consistency_score"] == 100.0
    assert case["entities"]["version"] == "entity_summary_v1"
    assert case["timeline"]["schema"] == "relluna.read_model.timeline.document.v2"
    assert case["review"]["version"] == "review_items_v1"
    assert case["legal"]["canonical_fields"]["schema_version"] == "legal_canonical_fields_v1"
    assert case["provenance"]["source_signals"] == [
        "entities_canonical_v1",
        "legal_canonical_fields_v1",
        "timeline_seed_v2",
        "layer3.eventos_probatorios",
        "layer5.read_models.entity_summary_v1",
        "layer5.read_models.review_items_v1",
    ]


def test_case_endpoint_returns_minimal_case_view():
    fake_mongo_store.clear()
    dm = _case_dm()
    fake_mongo_store._STORE[dm.layer0.documentid] = dm.model_dump(mode="python")

    payload = asyncio.run(get_document_case(dm.layer0.documentid))

    assert payload["schema"] == "relluna.read_model.case.document.v1"
    assert payload["document"]["doc_type"] == "atestado_medico"
    assert payload["entities"]["people"]["patient"] == "MARIA SILVA"
    assert payload["timeline"]["timeline"][0]["event_id"] == "event-1"
    assert payload["review"]["total_items"] >= 1
    assert payload["legal"]["summary"]["total_canonical_fields"] == 1
    assert payload["summary"]["warnings"] == []
