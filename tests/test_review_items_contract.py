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
from relluna.services.derivatives.layer5 import apply_layer5
from relluna.services.entities.entities_canonical_v1 import apply_entities_canonical_v1


def _review_dm() -> DocumentMemory:
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="review-items-policy",
            contentfingerprint="3" * 64,
            ingestionagent="pytest",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="artifact-1",
                    tipo=ArtefatoTipo.original,
                    uri="memory://review-items.pdf",
                    hash_sha256="3" * 64,
                )
            ],
        ),
        layer2=Layer2Evidence(),
        layer3=Layer3Evidence(),
    )

    page_evidence = [
        {
            "page": 1,
            "page_text": (
                "Nome: MARIA SILVA\n"
                "Nome da mãe: JOSEFA SILVA\n"
                "Prestador: DRA ANA LIMA CRM 12345 SP\n"
                "CID: M54.5\n"
                "Data: 05/03/2024\n"
            ),
            "page_taxonomy": {"value": "parecer_medico"},
            "people": {
                "patient_name": "MARIA SILVA",
                "patient_confidence": 0.90,
                "patient_review_state": "review_recommended",
                "mother_name": "JOSEFA SILVA",
                "mother_confidence": 0.85,
                "mother_review_state": "review_recommended",
                "provider_name": "DRA ANA LIMA",
                "provider_confidence": 0.94,
                "provider_review_state": "review_recommended",
            },
            "administrative_entities": {"crm": ["CRM 12345 SP"]},
            "anchors": [
                {
                    "label": "patient",
                    "snippet": "Nome: MARIA SILVA",
                    "bbox": None,
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "mother",
                    "snippet": "Nome da mãe: JOSEFA SILVA",
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
            "clinical_entities": {"cids": ["M54.5"]},
        }
    ]

    dm.layer2.sinais_documentais["page_evidence_v1"] = ProvenancedString(
        valor=json.dumps(page_evidence, ensure_ascii=False),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )
    dm = apply_entities_canonical_v1(dm)

    exact_citation = EvidenceRef(
        source_path="layer2.sinais_documentais.timeline_seed_v2",
        page=1,
        bbox=[10, 20, 30, 40],
        snippet="Data: 06/03/2024",
        confidence=0.95,
        provenance_status="exact",
        review_state="auto_confirmed",
    )
    estimated_citation = EvidenceRef(
        source_path="layer2.sinais_documentais.entities_canonical_v1",
        page=1,
        bbox=None,
        snippet="afastado(a) por 10 dia(s), a partir desta data",
        confidence=0.8,
        provenance_status="estimated",
        review_state="review_recommended",
    )
    dm.layer3.eventos_probatorios = [
        ProbatoryEvent(
            event_id="event-doc-date",
            event_type="document_issue_date",
            title="Data de emissão",
            description="Data documental inferida a partir do Layer3.",
            date_iso="2024-03-06",
            confidence=0.95,
            review_state="auto_confirmed",
            provenance_status="exact",
            citations=[exact_citation],
        ),
        ProbatoryEvent(
            event_id="event-estimated",
            event_type="afastamento_fim_estimado",
            title="Fim estimado do afastamento",
            description="Evento estimado sem bbox exato.",
            date_iso="2024-03-15",
            confidence=0.80,
            review_state="review_recommended",
            provenance_status="estimated",
            citations=[estimated_citation],
        ),
    ]
    dm.layer2.sinais_documentais["timeline_seed_v2"] = ProvenancedString(
        valor=json.dumps(
            [
                {
                    "seed_id": "seed-doc-date",
                    "date_iso": "2024-03-05",
                    "date_literal": "05/03/2024",
                    "event_hint": "document_issue_date",
                    "include_in_timeline": True,
                    "page": 1,
                    "bbox": None,
                    "snippet": "Data: 05/03/2024",
                    "source": "entities_canonical_v1",
                    "source_path": "layer2.sinais_documentais.entities_canonical_v1",
                    "confidence": 0.82,
                    "review_state": "review_recommended",
                    "provenance_status": "text_fallback",
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


def _item_by_field(review_model: dict, field: str) -> dict:
    for item in review_model["items"]:
        if item["field"] == field:
            return item
    raise AssertionError(f"review item not found for field={field}")


def _event_item(review_model: dict, event_type: str) -> dict:
    for item in review_model["items"]:
        if item["item_type"] == "event" and item["field"] == event_type:
            return item
    raise AssertionError(f"review event item not found for event_type={event_type}")


def test_review_items_v1_contract_surfaces_human_review_payload():
    dm = apply_layer5(_review_dm())
    review_model = dm.layer5.read_models["review_items_v1"]

    assert review_model["version"] == "review_items_v1"
    assert review_model["document_id"] == "review-items-policy"
    assert review_model["document_type"] == "parecer_medico"
    assert review_model["artifact_uri"] == "memory://review-items.pdf"
    assert review_model["total_items"] >= 6
    assert review_model["needs_review_count"] >= 4


def test_review_items_v1_includes_document_date_with_text_fallback():
    dm = apply_layer5(_review_dm())
    review_model = dm.layer5.read_models["review_items_v1"]
    item = _item_by_field(review_model, "document_date")

    assert item["item_type"] == "document_date"
    assert item["value"] == "2024-03-05"
    assert item["provenance_status"] == "text_fallback"
    assert item["review_state"] == "review_recommended"
    assert item["reason"] == "date_candidate_not_birth_context"
    assert item["source_signal"] == "entities_canonical_v1.semantic_resolution_v1.document_date"
    assert item["suggested_action"] == "confirm_with_document_evidence"
    assert item["evidence_refs"][0]["bbox"] is None


def test_review_items_v1_includes_patient_with_text_fallback():
    dm = apply_layer5(_review_dm())
    review_model = dm.layer5.read_models["review_items_v1"]
    item = _item_by_field(review_model, "patient")

    assert item["item_type"] == "person"
    assert item["value"] == "MARIA SILVA"
    assert item["provenance_status"] == "text_fallback"
    assert item["review_state"] == "review_recommended"
    assert item["reason"] == "patient_anchor_candidate"
    assert item["source_signal"] == "entities_canonical_v1.semantic_resolution_v1.people"
    assert item["evidence_refs"][0]["bbox"] is None


def test_review_items_v1_flags_estimated_event():
    dm = apply_layer5(_review_dm())
    review_model = dm.layer5.read_models["review_items_v1"]
    item = _event_item(review_model, "afastamento_fim_estimado")

    assert item["value"]["event_id"] == "event-estimated"
    assert item["provenance_status"] == "estimated"
    assert item["review_state"] == "review_recommended"
    assert item["reason"] == "estimated_probatory_event"
    assert item["source_signal"] == "layer3.eventos_probatorios"
    assert item["suggested_action"] == "confirm_estimated_event_bounds"
    assert item["evidence_refs"][0]["bbox"] is None


def test_review_items_v1_flags_seed_vs_layer3_conflict():
    dm = apply_layer5(_review_dm())
    review_model = dm.layer5.read_models["review_items_v1"]
    item = _item_by_field(review_model, "timeline_seed_vs_layer3")

    assert item["item_type"] == "conflict"
    assert item["provenance_status"] == "conflict"
    assert item["review_state"] == "needs_review"
    assert item["reason"] == "timeline_seed_v2_layer3_divergence"
    assert item["source_signal"] == "timeline_consistency_v1"
    assert item["suggested_action"] == "reconcile_timeline_sources"
    assert item["value"]["seed_event_count"] == 1
    assert item["value"]["layer3_event_count"] == 2


def test_review_items_v1_marks_weak_provider_evidence_as_needs_review():
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="review-items-provider-weak",
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
                    uri="memory://review-items-provider-weak.pdf",
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
            "page_text": (
                "LAUDO MEDICO\n"
                "Paciente: ALICE MARTINS\n"
                "Prestador: DR. GUSTAVO LEAL\n"
                "São Paulo, 03/07/2024\n"
            ),
            "page_taxonomy": {"value": "laudo_medico"},
            "people": {
                "patient_name": "ALICE MARTINS",
                "patient_confidence": 0.94,
                "patient_review_state": "review_recommended",
                "provider_name": "DR. GUSTAVO LEAL",
                "provider_confidence": 0.78,
                "provider_review_state": "review_recommended",
            },
            "anchors": [
                {
                    "label": "patient",
                    "snippet": "Paciente: ALICE MARTINS",
                    "bbox": [68, 118, 248, 138],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "provider",
                    "snippet": "São Paulo, 03/07/2024",
                    "bbox": None,
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
            ],
            "date_candidates": [
                {"literal": "03/07/2024", "date_iso": "2024-07-03"},
            ],
            "administrative_entities": {"crm": []},
            "clinical_entities": {"cids": []},
        }
    ]

    dm.layer2.sinais_documentais["page_evidence_v1"] = ProvenancedString(
        valor=json.dumps(page_evidence, ensure_ascii=False),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )

    dm = apply_layer5(apply_entities_canonical_v1(dm))
    review_model = dm.layer5.read_models["review_items_v1"]
    item = _item_by_field(review_model, "provider")

    assert item["value"] == "DR. GUSTAVO LEAL"
    assert item["review_state"] == "needs_review"
    assert item["provenance_status"] == "text_fallback"
    assert item["evidence_refs"][0]["page"] == 1
    assert item["evidence_refs"][0]["bbox"] is None
    assert item["evidence_refs"][0]["snippet"] == "provider: DR. GUSTAVO LEAL"
