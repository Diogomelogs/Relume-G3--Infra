from datetime import datetime, timezone
import json
from relluna.core.document_memory import DocumentMemory, Layer0Custodia, Layer1Artefatos, Layer2Evidence, ArtefatoBruto, MediaType, OriginType
from relluna.core.document_memory.layer3 import ProbatoryEvent
from relluna.core.document_memory.types_basic import ConfidenceState, EvidenceRef, ProvenancedString
from relluna.services.read_model.projector import project_dm_to_read_model


def _dm_minimo():
    return DocumentMemory(
        layer0=Layer0Custodia(
            documentid="doc-1",
            contentfingerprint="e" * 64,
            ingestiontimestamp=datetime.now(timezone.utc),
            ingestionagent="test",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[ArtefatoBruto(id="a1", tipo="original", uri="file:///tmp/a.pdf")],
        ),
        layer2=Layer2Evidence(
            sinais_documentais={
                "timeline_seed_v2": ProvenancedString(
                    valor=json.dumps(
                        [
                            {
                                "seed_id": "seed-1",
                                "date_iso": "2008-10-22",
                                "event_hint": "document_issue_date",
                                "page": 1,
                                "bbox": [1, 2, 3, 4],
                                "snippet": "Data: 22/10/2008",
                                "provenance_status": "exact",
                                "review_state": "auto_confirmed",
                            }
                        ]
                    ),
                    fonte="pytest",
                    metodo="fixture",
                    estado=ConfidenceState.confirmado,
                    confianca=1.0,
                )
            }
        ),
        layer3={
            "eventos_probatorios": [
                ProbatoryEvent(
                    event_id="ev-1",
                    event_type="document_issue_date",
                    title="Data de emissão",
                    date_iso="2008-10-22",
                    confidence=0.95,
                    review_state="auto_confirmed",
                    provenance_status="exact",
                    citations=[
                        EvidenceRef(
                            source_path="layer2.sinais_documentais.timeline_seed_v2",
                            page=1,
                            bbox=[1, 2, 3, 4],
                            snippet="Data: 22/10/2008",
                            confidence=0.95,
                            provenance_status="exact",
                            review_state="auto_confirmed",
                        )
                    ],
                )
            ],
            "tipo_documento": {"valor": "parecer_medico"},
        },
        layer4={
            "date_canonical": "2008-10-22",
            "period_label": "2008-10",
            "tags": ["familia", "viagem"],
            "entities": [{"kind": "pessoa", "label": "mãe"}],
        },
        layer5=None,
        layer6=None,
    )


def test_projector_creates_read_model_minimum():
    dm = _dm_minimo()
    rm = project_dm_to_read_model(dm)

    assert rm.document_id == "doc-1"
    assert rm.media_type == "documento"
    assert rm.title
    assert rm.summary
    assert rm.date_canonical == "2008-10-22"
    assert rm.period_label == "2008-10"
    assert "familia" in rm.tags
    assert any(e.label == "mãe" for e in rm.entities)
    assert rm.doc_type == "parecer_medico"
    assert rm.timeline.endpoint == "/documents/doc-1/timeline"
    assert rm.timeline.total_events == 1
    assert rm.timeline.anchored_events == 1
    assert rm.confidence_indicators["timeline_consistency_score"] == 100.0
    assert "event:document_issue_date" in rm.tags
    assert rm.search_text  # sempre preenchido


def test_projector_never_invents_date():
    dm = _dm_minimo()
    dm.layer4 = {}  # sem normalização
    rm = project_dm_to_read_model(dm)
    assert rm.date_canonical is None
    assert rm.period_label is None
