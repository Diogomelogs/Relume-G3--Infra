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
from relluna.core.document_memory.types_basic import ConfidenceState, ProvenancedString
from relluna.services.context_inference.basic import infer_layer3
from relluna.services.deterministic_extractors.timeline_seed_v2 import seed_timeline_v2
from relluna.services.entities.entities_canonical_v1 import apply_entities_canonical_v1
from relluna.services.read_model.timeline_builder import build_document_timeline_read_model


def _signal(payload) -> ProvenancedString:
    return ProvenancedString(
        valor=json.dumps(payload, ensure_ascii=False),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )


def _page(
    *,
    page: int,
    subdoc_id: str,
    page_text: str,
    document_type: str,
    patient: str | None = None,
    provider: str | None = None,
    date_iso: str | None = None,
    date_literal: str | None = None,
    cids: list[str] | None = None,
) -> dict:
    anchors = []
    if patient:
        anchors.append(
            {
                "label": "patient",
                "value": patient,
                "page": page,
                "bbox": [10, 10, 200, 24],
                "snippet": f"Paciente: {patient}",
                "source_path": "layer2.sinais_documentais.page_evidence_v1",
            }
        )
    if provider:
        anchors.append(
            {
                "label": "provider",
                "value": provider,
                "page": page,
                "bbox": [10, 30, 230, 44],
                "snippet": f"{provider} CRM 12345 SP",
                "source_path": "layer2.sinais_documentais.page_evidence_v1",
            }
        )
    if date_iso and date_literal:
        anchors.append(
            {
                "label": "date",
                "value": date_iso,
                "page": page,
                "bbox": [10, 50, 120, 64],
                "snippet": date_literal,
                "source_path": "layer2.sinais_documentais.page_evidence_v1",
            }
        )
    for index, cid in enumerate(cids or []):
        anchors.append(
            {
                "label": "cid",
                "value": cid,
                "page": page,
                "bbox": [10, 70 + (index * 20), 90, 84 + (index * 20)],
                "snippet": f"CID {cid}",
                "source_path": "layer2.sinais_documentais.page_evidence_v1",
            }
        )

    return {
        "page": page,
        "subdoc_id": subdoc_id,
        "page_text": page_text,
        "page_taxonomy": {"value": document_type},
        "people": {
            "patient_name": patient,
            "patient_confidence": 0.97 if patient else None,
            "patient_review_state": "auto_confirmed" if patient else "needs_review",
            "provider_name": provider,
            "provider_confidence": 0.93 if provider else None,
            "provider_review_state": "review_recommended" if provider else "needs_review",
        },
        "administrative_entities": {
            "crm": [f"CRM 12345 SP"] if provider else [],
        },
        "date_candidates": (
            [{"literal": date_literal, "date_iso": date_iso}] if date_iso and date_literal else []
        ),
        "clinical_entities": {
            "provider_name": provider,
            "cids": cids or [],
        },
        "anchors": anchors,
        "signal_zones": [
            {
                "label": anchor["label"],
                "value": anchor["value"],
                "page": page,
                "bbox": anchor["bbox"],
                "snippet": anchor["snippet"],
                "signal_zone": "core_probative",
                "confidence": 0.97,
                "review_state": "auto_confirmed",
                "provenance_status": "exact",
                "source_path": anchor["source_path"],
            }
            for anchor in anchors
        ],
    }


def _heterogeneous_dm() -> DocumentMemory:
    page_evidence = [
        _page(
            page=1,
            subdoc_id="subdoc_a",
            page_text="RECEITUARIO\nPaciente: ALICE SOARES\nDR. XAVIER LIMA CRM 12345 SP\nData: 10/01/2024\n",
            document_type="receituario",
            patient="ALICE SOARES",
            provider="DR. XAVIER LIMA",
            date_iso="2024-01-10",
            date_literal="10/01/2024",
        ),
        _page(
            page=2,
            subdoc_id="subdoc_a",
            page_text="Continuação receituário\nPaciente: ALICE SOARES\nDR. XAVIER LIMA CRM 12345 SP\nData: 10/01/2024\n",
            document_type="receituario",
            patient="ALICE SOARES",
            provider="DR. XAVIER LIMA",
            date_iso="2024-01-10",
            date_literal="10/01/2024",
        ),
        _page(
            page=3,
            subdoc_id="subdoc_b",
            page_text="PARECER MEDICO\nPaciente: ALICE SOARES\nDR. BRAVO COSTA CRM 12345 SP\nData: 25/01/2024\nCID M51.1\n",
            document_type="parecer_medico",
            patient="ALICE SOARES",
            provider="DR. BRAVO COSTA",
            date_iso="2024-01-25",
            date_literal="25/01/2024",
            cids=["M51.1"],
        ),
        _page(
            page=4,
            subdoc_id="subdoc_b",
            page_text="PARECER MEDICO CONT.\nPaciente: ALICE SOARES\nDR. BRAVO COSTA CRM 12345 SP\nData: 25/01/2024\nCID M51.1\n",
            document_type="parecer_medico",
            patient="ALICE SOARES",
            provider="DR. BRAVO COSTA",
            date_iso="2024-01-25",
            date_literal="25/01/2024",
            cids=["M51.1"],
        ),
        _page(
            page=5,
            subdoc_id="subdoc_c",
            page_text="RECEITUARIO\nPaciente: ALICE SOARES\nDR. XAVIER LIMA CRM 12345 SP\nData: 10/01/2024\n",
            document_type="receituario",
            patient="ALICE SOARES",
            provider="DR. XAVIER LIMA",
            date_iso="2024-01-10",
            date_literal="10/01/2024",
        ),
        _page(
            page=6,
            subdoc_id="subdoc_c",
            page_text="RECEITUARIO CONT.\nPaciente: ALICE SOARES\nDR. XAVIER LIMA CRM 12345 SP\nData: 10/01/2024\n",
            document_type="receituario",
            patient="ALICE SOARES",
            provider="DR. XAVIER LIMA",
            date_iso="2024-01-10",
            date_literal="10/01/2024",
        ),
        _page(
            page=7,
            subdoc_id="subdoc_d",
            page_text="RECEITUARIO\nPaciente: BRUNO PEREIRA\nDR. XAVIER LIMA CRM 12345 SP\nData: 10/01/2024\n",
            document_type="receituario",
            patient="BRUNO PEREIRA",
            provider="DR. XAVIER LIMA",
            date_iso="2024-01-10",
            date_literal="10/01/2024",
        ),
        _page(
            page=8,
            subdoc_id="subdoc_e",
            page_text="EXAME COMPLEMENTAR\nMaterial insuficiente para identificar paciente e médico.\n",
            document_type="laudo_medico",
        ),
    ]
    subdocuments = [
        {"subdoc_id": "subdoc_a", "doc_type": "receituario", "page_map": [{"page": 1, "text": page_evidence[0]["page_text"]}, {"page": 2, "text": page_evidence[1]["page_text"]}]},
        {"subdoc_id": "subdoc_b", "doc_type": "parecer_medico", "page_map": [{"page": 3, "text": page_evidence[2]["page_text"]}, {"page": 4, "text": page_evidence[3]["page_text"]}]},
        {"subdoc_id": "subdoc_c", "doc_type": "receituario", "page_map": [{"page": 5, "text": page_evidence[4]["page_text"]}, {"page": 6, "text": page_evidence[5]["page_text"]}]},
        {"subdoc_id": "subdoc_d", "doc_type": "receituario", "page_map": [{"page": 7, "text": page_evidence[6]["page_text"]}]},
        {"subdoc_id": "subdoc_e", "doc_type": "laudo_medico", "page_map": [{"page": 8, "text": page_evidence[7]["page_text"]}]},
    ]

    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="epistemic-segmentation",
            contentfingerprint="9" * 64,
            ingestionagent="pytest",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="artifact-epistemic-segmentation",
                    tipo=ArtefatoTipo.original,
                    uri="memory://epistemic-segmentation.pdf",
                    hash_sha256="9" * 64,
                )
            ],
        ),
        layer2=Layer2Evidence(),
        layer3=Layer3Evidence(),
    )
    dm.layer2.sinais_documentais["page_evidence_v1"] = _signal(page_evidence)
    dm.layer2.sinais_documentais["subdocuments_v1"] = _signal(subdocuments)
    dm.layer2.texto_ocr_literal = ProvenancedString(
        valor="\n\n".join(item["page_text"] for item in page_evidence),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )
    return dm


def test_epistemic_page_and_subdocument_units_prevent_global_collapse():
    dm = apply_entities_canonical_v1(_heterogeneous_dm())

    page_units = json.loads(dm.layer2.sinais_documentais["page_unit_v1"].valor)
    subdocument_units = json.loads(dm.layer2.sinais_documentais["subdocument_unit_v1"].valor)
    relation_graph = json.loads(dm.layer2.sinais_documentais["document_relation_graph_v1"].valor)

    assert len(page_units) == 8
    assert len(subdocument_units) == 5

    page1 = next(unit for unit in page_units if unit["page_index"] == 1)
    page7 = next(unit for unit in page_units if unit["page_index"] == 7)
    page8 = next(unit for unit in page_units if unit["page_index"] == 8)
    assert page1["patient"]["name"] == "ALICE SOARES"
    assert page7["patient"]["name"] == "BRUNO PEREIRA"
    assert "patient_unknown" in page8["uncertainties"]
    assert page1["provider"]["name"] != page7["patient"]["name"]

    subdoc_a = next(unit for unit in subdocument_units if unit["subdoc_id"] == "subdoc_a")
    subdoc_b = next(unit for unit in subdocument_units if unit["subdoc_id"] == "subdoc_b")
    subdoc_d = next(unit for unit in subdocument_units if unit["subdoc_id"] == "subdoc_d")
    subdoc_e = next(unit for unit in subdocument_units if unit["subdoc_id"] == "subdoc_e")
    assert subdoc_a["provider"]["name"] == "DR. XAVIER LIMA"
    assert subdoc_b["provider"]["name"] == "DR. BRAVO COSTA"
    assert subdoc_d["patient"]["name"] == "BRUNO PEREIRA"
    assert "patient_unknown" in subdoc_e["uncertainties"]

    relation_types = {
        (edge["source_subdoc_id"], edge["target_subdoc_id"], edge["relation_type"])
        for edge in relation_graph["edges"]
    }
    assert ("subdoc_a", "subdoc_b", "same_patient") in relation_types
    assert ("subdoc_a", "subdoc_b", "same_episode") in relation_types
    assert ("subdoc_a", "subdoc_c", "same_document_continuation") in relation_types
    assert ("subdoc_a", "subdoc_d", "conflict") in relation_types
    assert ("subdoc_a", "subdoc_e", "unknown") in relation_types


def test_timeline_seeds_and_public_read_model_are_segmented_and_expose_conflicts():
    dm = _heterogeneous_dm()
    dm = apply_entities_canonical_v1(dm)
    dm = seed_timeline_v2(dm)
    dm = infer_layer3(dm)

    seeds = json.loads(dm.layer2.sinais_documentais["timeline_seed_v2"].valor)
    seed_keys = {(seed["subdoc_id"], seed["event_hint"], seed["date_iso"]) for seed in seeds}
    assert ("subdoc_a", "document_issue_date", "2024-01-10") in seed_keys
    assert ("subdoc_b", "parecer_emitido", "2024-01-25") in seed_keys
    assert ("subdoc_b", "registro_condicao_clinica", "2024-01-25") in seed_keys
    assert ("subdoc_c", "document_issue_date", "2024-01-10") in seed_keys
    assert ("subdoc_d", "document_issue_date", "2024-01-10") in seed_keys
    assert not any(seed.get("subdoc_id") == "subdoc_e" for seed in seeds)
    assert all(seed.get("assertion_level") in {"observed", "inferred", "unknown"} for seed in seeds)

    timeline = build_document_timeline_read_model(dm)
    event_keys = {(event["subdoc_id"], event["event_type"], event["date"]) for event in timeline["timeline"]}
    assert ("subdoc_a", "document_issue_date", "2024-01-10") in event_keys
    assert ("subdoc_b", "parecer_emitido", "2024-01-25") in event_keys
    assert ("subdoc_b", "registro_condicao_clinica", "2024-01-25") in event_keys
    assert ("subdoc_c", "document_issue_date", "2024-01-10") in event_keys
    assert ("subdoc_d", "document_issue_date", "2024-01-10") in event_keys
    assert timeline["summary"]["subdocument_count"] == 5
    assert timeline["summary"]["relation_conflict_count"] >= 1
    assert timeline["summary"]["relation_unknown_count"] >= 1
    assert len(timeline["subdocuments"]) == 5
    assert any(item["relation_type"] == "conflict" for item in timeline["inconsistencies"])
    assert any(item["relation_type"] == "unknown" for item in timeline["inconsistencies"])
    assert all(event["assertion_level"] in {"observed", "inferred", "unknown"} for event in timeline["timeline"])
