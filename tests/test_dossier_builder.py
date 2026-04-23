from __future__ import annotations

import json
from datetime import datetime, timezone

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
from relluna.services.derivatives.layer5 import apply_layer5
from relluna.services.entities.entities_canonical_v1 import apply_entities_canonical_v1
from relluna.services.export.dossier_builder import build_dossier_payload


def _build_dm() -> DocumentMemory:
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="dossier-doc",
            contentfingerprint="4" * 64,
            ingestiontimestamp=datetime.now(timezone.utc),
            ingestionagent="pytest",
            original_filename="dossier.pdf",
            mimetype="application/pdf",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="artifact-dossier",
                    tipo=ArtefatoTipo.original,
                    uri="memory://dossier.pdf",
                    nome="dossier.pdf",
                    mimetype="application/pdf",
                    tamanho_bytes=12345,
                    hash_sha256="4" * 64,
                    is_persisted=False,
                )
            ],
        ),
        layer2=Layer2Evidence(),
        layer3=Layer3Evidence(),
    )
    dm.layer2.sinais_documentais["page_evidence_v1"] = ProvenancedString(
        valor=json.dumps(
            [
                {
                    "page": 1,
                    "page_text": "Paciente: MARIA SILVA\nPrestador: DRA ANA LIMA\nCID: M54.5\nData: 05/03/2024",
                    "page_taxonomy": {"value": "parecer_medico"},
                    "people": {
                        "patient_name": "MARIA SILVA",
                        "patient_confidence": 0.9,
                        "patient_review_state": "review_recommended",
                        "provider_name": "DRA ANA LIMA",
                        "provider_confidence": 0.94,
                        "provider_review_state": "review_recommended",
                    },
                    "anchors": [
                        {
                            "label": "patient",
                            "snippet": "Paciente: MARIA SILVA",
                            "bbox": None,
                            "source_path": "layer2.sinais_documentais.page_evidence_v1",
                        }
                    ],
                    "date_candidates": [{"literal": "05/03/2024", "date_iso": "2024-03-05"}],
                    "clinical_entities": {"cids": ["M54.5"]},
                }
            ],
            ensure_ascii=False,
        ),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )
    dm = apply_entities_canonical_v1(dm)
    dm.layer3.eventos_probatorios = [
        ProbatoryEvent(
            event_id="event-observed",
            event_type="document_issue_date",
            title="Data de emissão",
            description="Data documental observada no documento.",
            date_iso="2024-03-05",
            confidence=0.95,
            review_state="auto_confirmed",
            provenance_status="exact",
            citations=[
                EvidenceRef(
                    source_path="layer2.sinais_documentais.timeline_seed_v2",
                    page=1,
                    bbox=[10, 20, 30, 40],
                    snippet="Data: 05/03/2024",
                    confidence=0.95,
                    provenance_status="exact",
                    review_state="auto_confirmed",
                )
            ],
            entities={"patient": "MARIA SILVA"},
        ),
        ProbatoryEvent(
            event_id="event-estimated",
            event_type="afastamento_fim_estimado",
            title="Fim estimado do afastamento",
            description="Evento calculado a partir da duração do afastamento.",
            date_iso="2024-03-15",
            confidence=0.8,
            review_state="review_recommended",
            provenance_status="estimated",
            citations=[
                EvidenceRef(
                    source_path="layer2.sinais_documentais.entities_canonical_v1",
                    page=1,
                    bbox=None,
                    snippet="afastado(a) por 10 dia(s)",
                    confidence=0.8,
                    provenance_status="estimated",
                    review_state="review_recommended",
                )
            ],
            entities={"patient": "MARIA SILVA"},
        ),
        ProbatoryEvent(
            event_id="event-inferred",
            event_type="parecer_emitido",
            title="Emissão de parecer",
            description="Evento inferido sem bbox exato.",
            date_iso="2024-03-05",
            confidence=0.86,
            review_state="review_recommended",
            provenance_status="inferred",
            citations=[
                EvidenceRef(
                    source_path="layer2.texto_ocr_literal.valor",
                    page=1,
                    bbox=None,
                    snippet="parecer médico emitido",
                    confidence=0.86,
                    provenance_status="inferred",
                    review_state="review_recommended",
                )
            ],
            entities={"patient": "MARIA SILVA"},
        ),
    ]
    dm.layer2.sinais_documentais["timeline_seed_v2"] = ProvenancedString(
        valor=json.dumps(
            [
                {
                    "seed_id": "seed-observed",
                    "date_iso": "2024-03-05",
                    "event_hint": "document_issue_date",
                    "page": 1,
                    "bbox": [10, 20, 30, 40],
                    "snippet": "Data: 05/03/2024",
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
    return apply_layer5(dm)


def test_build_dossier_payload_has_minimum_audit_shape():
    dossier = build_dossier_payload(_build_dm())

    assert dossier["version"] == "dossier_auditavel_v1"
    assert dossier["document"]["document_id"] == "dossier-doc"
    assert dossier["document"]["content_fingerprint"] == "4" * 64
    assert dossier["document"]["artifact"]["uri"] == "memory://dossier.pdf"
    assert dossier["document"]["artifact"]["is_persisted"] is False
    assert dossier["summary"]["persistence_state"] == "placeholder_not_persisted"
    assert dossier["entities"]["patient"] == "MARIA SILVA"
    assert "Derivados placeholder" in dossier["disclaimers"][0]


def test_build_dossier_payload_marks_inferred_and_estimated_events_explicitly():
    dossier = build_dossier_payload(_build_dm())
    by_type = {event["event_type"]: event for event in dossier["timeline"]}

    assert by_type["document_issue_date"]["assertion_level"] == "observed"
    assert by_type["document_issue_date"]["provenance_status"] == "exact"

    assert by_type["afastamento_fim_estimado"]["assertion_level"] == "estimated"
    assert by_type["afastamento_fim_estimado"]["provenance_status"] == "estimated"
    assert by_type["afastamento_fim_estimado"]["review_state"] == "review_recommended"

    assert by_type["parecer_emitido"]["assertion_level"] == "inferred"
    assert by_type["parecer_emitido"]["provenance_status"] == "inferred"
    assert by_type["parecer_emitido"]["citations"][0]["bbox"] is None
