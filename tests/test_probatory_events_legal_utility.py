import json

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
from relluna.services.context_inference.basic import infer_layer3


def _signal(value):
    return ProvenancedString(
        valor=json.dumps(value, ensure_ascii=False),
        fonte="test",
        metodo="fixture",
        estado="confirmado",
        confianca=1.0,
    )


def _document_memory_with_signals(signals):
    return DocumentMemory(
        layer0=Layer0Custodia(
            documentid="doc-probatory-events",
            contentfingerprint="a" * 64,
            ingestionagent="pytest",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="artifact-1",
                    tipo=ArtefatoTipo.original,
                    uri="memory://doc-probatory-events.pdf",
                )
            ],
        ),
        layer2=Layer2Evidence(
            texto_ocr_literal=ProvenancedString(
                valor="PARECER MEDICO CRM 12345. Data 05/03/2024. Afastado por 5 dia(s).",
                fonte="test",
                metodo="fixture",
                estado="confirmado",
                confianca=1.0,
            ),
            sinais_documentais=signals,
        ),
    )


def test_probatory_events_have_legal_provenance_review_confidence_and_evidence():
    dm = _document_memory_with_signals(
        {
            "entities_canonical_v1": _signal(
                {
                    "document_type": "parecer_medico",
                    "patient": {"name": "MARCOS ANTONIO REIS", "confidence": 0.98},
                    "provider": {"name": "DRA JULIA MARTINS", "confidence": 0.96},
                    "clinical": {"cids": [{"code": "S83.2", "confidence": 0.97}]},
                }
            ),
            "page_evidence_v1": _signal(
                [
                    {
                        "page": 1,
                        "signal_zones": [
                            {
                                "page": 1,
                                "signal_zone": "core_probative",
                                "label": "document_date",
                                "snippet": "Data 05/03/2024",
                                "bbox": [10, 20, 100, 40],
                                "confidence": 0.95,
                                "provenance_status": "exact",
                            }
                        ],
                    }
                ]
            ),
            "timeline_seed_v2": _signal(
                [
                    {
                        "seed_id": "seed-exact",
                        "date_iso": "2024-03-05",
                        "date_literal": "05/03/2024",
                        "event_hint": "document_issue_date",
                        "include_in_timeline": True,
                        "confidence": 0.93,
                        "source": "timeline_seed_v2",
                        "source_path": "layer2.sinais_documentais.timeline_seed_v2[0]",
                        "page": 1,
                        "bbox": [10, 20, 100, 40],
                        "snippet": "Data 05/03/2024",
                    },
                    {
                        "seed_id": "seed-inferred",
                        "date_iso": "2024-03-05",
                        "date_literal": "05/03/2024",
                        "event_hint": "parecer_emitido",
                        "include_in_timeline": True,
                        "confidence": 0.82,
                        "source": "timeline_seed_v2",
                        "source_path": "layer2.sinais_documentais.timeline_seed_v2[1]",
                        "page": 2,
                        "snippet": "Parecer médico emitido em 05/03/2024",
                    },
                    {
                        "seed_id": "seed-estimated",
                        "date_iso": "2024-03-10",
                        "date_literal": "10/03/2024",
                        "event_hint": "afastamento_fim_estimado",
                        "include_in_timeline": True,
                        "confidence": 0.81,
                        "source": "timeline_seed_v2",
                        "source_path": "layer2.sinais_documentais.timeline_seed_v2[2]",
                        "page": 2,
                        "snippet": "Afastado por 5 dia(s)",
                    },
                ]
            ),
        }
    )

    infer_layer3(dm)

    events = {
        event.event_type: event
        for event in dm.layer3.eventos_probatorios
    }
    assert set(events) == {
        "document_issue_date",
        "parecer_emitido",
        "afastamento_fim_estimado",
    }

    for event in events.values():
        assert event.confidence is not None
        assert 0.0 <= event.confidence <= 1.0
        assert event.review_state in {
            "auto_confirmed",
            "review_recommended",
            "needs_review",
        }
        assert event.provenance_status in {"exact", "inferred", "estimated"}
        assert event.entities["patient"] == "MARCOS ANTONIO REIS"
        assert event.citations
        assert event.citations[0].page is not None
        assert event.citations[0].snippet

    exact = events["document_issue_date"]
    assert exact.provenance_status == "exact"
    assert exact.review_state == "auto_confirmed"
    assert exact.citations[0].bbox == [10.0, 20.0, 100.0, 40.0]

    inferred = events["parecer_emitido"]
    assert inferred.provenance_status == "inferred"
    assert inferred.citations[0].bbox is None

    estimated = events["afastamento_fim_estimado"]
    assert estimated.provenance_status == "estimated"
    assert estimated.citations[0].bbox is None
