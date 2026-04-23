from __future__ import annotations

import json
from datetime import datetime, timezone

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.layer0 import Layer0Custodia
from relluna.core.document_memory.layer2 import Layer2Evidence
from relluna.core.document_memory.types_basic import ConfidenceState, ProvenancedString
from relluna.services.entities.entities_canonical_v1 import apply_entities_canonical_v1
from relluna.services.evidence.signals import load_critical_signal_json
from relluna.services.legal.case_engine import build_case_outputs
from relluna.services.legal.legal_canonical_fields_v1 import apply_legal_canonical_fields_v1


def _dm() -> DocumentMemory:
    return DocumentMemory(
        layer0=Layer0Custodia(
            documentid="legal-canonical-test",
            contentfingerprint="8" * 64,
            ingestiontimestamp=datetime.now(timezone.utc),
            ingestionagent="pytest",
        ),
        layer2=Layer2Evidence(),
    )


def _signal(payload) -> ProvenancedString:
    return ProvenancedString(
        valor=json.dumps(payload, ensure_ascii=False),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )


def _field_by_name(extraction: dict, name: str) -> dict:
    for field in extraction["fields"]:
        if field["name"] == name:
            return field
    raise AssertionError(f"field not found: {name}")


def test_apply_legal_canonical_fields_v1_projects_entities_canonical_without_mixing_assertions():
    dm = _dm()
    dm.layer2.sinais_documentais["entities_canonical_v1"] = _signal(
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
                "resolution": {"reason": "patient_anchor_candidate"},
            },
            "provider": {
                "name": "DRA ANA LIMA",
                "crm": "12345",
                "confidence": 0.94,
                "review_state": "review_recommended",
                "evidence": {
                    "page": 1,
                    "bbox": None,
                    "snippet": "Dra Ana Lima CRM 12345",
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                    "provenance_status": "snippet_only",
                },
                "resolution": {"reason": "provider_anchor_candidate"},
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
                "resolution": {"reason": "explicit_document_date"},
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
            "internacao": {
                "start": {
                    "date_iso": "2024-03-01",
                    "literal": "01/03/2024",
                    "confidence": 0.96,
                    "evidence": {
                        "page": 1,
                        "bbox": None,
                        "snippet": "internado(a) do dia 01/03/2024 ao dia 02/03/2024",
                        "source_path": "layer2.texto_ocr_literal.valor",
                        "provenance_status": "text_fallback",
                    },
                },
                "end": {
                    "date_iso": "2024-03-02",
                    "literal": "02/03/2024",
                    "confidence": 0.96,
                    "evidence": {
                        "page": 1,
                        "bbox": None,
                        "snippet": "internado(a) do dia 01/03/2024 ao dia 02/03/2024",
                        "source_path": "layer2.texto_ocr_literal.valor",
                        "provenance_status": "text_fallback",
                    },
                },
            },
            "afastamento": {
                "duration_days": {"value": 5, "confidence": 0.9},
                "start": {
                    "date_iso": "2024-03-02",
                    "literal": "02/03/2024",
                    "confidence": 0.9,
                    "evidence": {
                        "page": 1,
                        "bbox": None,
                        "snippet": "afastado(a) por 5 dia(s), a partir desta data",
                        "source_path": "layer2.texto_ocr_literal.valor",
                        "provenance_status": "inferred",
                    },
                },
                "estimated_end": {
                    "date_iso": "2024-03-07",
                    "literal": None,
                    "confidence": 0.8,
                    "evidence": {
                        "page": 1,
                        "bbox": None,
                        "snippet": "afastado(a) por 5 dia(s), a partir desta data",
                        "source_path": "layer2.texto_ocr_literal.valor",
                        "provenance_status": "inferred",
                    },
                },
            },
            "quality": {"warnings": ["provider_without_exact_bbox"]},
        }
    )

    dm = apply_legal_canonical_fields_v1(dm)
    extraction = load_critical_signal_json(dm, "legal_canonical_fields_v1")

    assert extraction["schema_version"] == "legal_canonical_fields_v1"
    assert extraction["source_signal"] == "entities_canonical_v1"
    assert extraction["doc_type"] == "atestado_medico"
    assert extraction["warnings"] == ["provider_without_exact_bbox"]

    assert _field_by_name(extraction, "Tipo_Documento")["assertion_level"] == "inferred"
    assert _field_by_name(extraction, "Nome_Paciente")["assertion_level"] == "observed"
    assert _field_by_name(extraction, "Data_Documento")["normalized_value"] == "2024-03-05"
    assert _field_by_name(extraction, "Data_Documento")["assertion_level"] == "observed"
    assert _field_by_name(extraction, "CRM_Medico")["value"] == "12345"
    assert _field_by_name(extraction, "CID_Atestado")["value"] == "M54.5"
    assert _field_by_name(extraction, "Afastamento_Inicio")["assertion_level"] == "inferred"
    assert _field_by_name(extraction, "Afastamento_Fim_Estimado")["assertion_level"] == "estimated"
    assert all(field["name"] != "Data_Nascimento" for field in extraction["fields"])


def test_apply_entities_canonical_v1_also_emits_legal_canonical_fields_v1():
    dm = _dm()
    dm.layer2.texto_ocr_literal = ProvenancedString(
        valor="ATESTADO MEDICO. Paciente: MARIA SILVA. Data: 05/03/2024. CID M54.5.",
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )
    dm.layer2.sinais_documentais["page_evidence_v1"] = _signal(
        [
            {
                "page": 1,
                "page_text": "ATESTADO MEDICO Paciente: MARIA SILVA Data: 05/03/2024 CID M54.5",
                "page_taxonomy": {"value": "atestado_medico"},
                "people": {
                    "patient_name": "MARIA SILVA",
                    "patient_confidence": 0.98,
                    "patient_review_state": "auto_confirmed",
                },
                "clinical_entities": {"cids": ["M54.5"]},
                "date_candidates": [
                    {
                        "role": "document_date_candidate",
                        "date_iso": "2024-03-05",
                        "literal": "05/03/2024",
                        "confidence": 0.97,
                        "page": 1,
                        "snippet": "Data: 05/03/2024",
                        "bbox": [150, 10, 210, 20],
                        "source_path": "layer2.sinais_documentais.page_evidence_v1",
                    }
                ],
                "anchors": [
                    {
                        "label": "patient",
                        "value": "MARIA SILVA",
                        "page": 1,
                        "snippet": "Paciente: MARIA SILVA",
                        "bbox": [10, 10, 120, 20],
                        "confidence": 0.98,
                        "source_path": "layer2.sinais_documentais.page_evidence_v1",
                        "provenance_status": "exact",
                    },
                    {
                        "label": "cid",
                        "value": "M54.5",
                        "page": 1,
                        "snippet": "CID M54.5",
                        "bbox": [220, 10, 280, 20],
                        "confidence": 0.95,
                        "source_path": "layer2.sinais_documentais.page_evidence_v1",
                        "provenance_status": "exact",
                    },
                ],
            }
        ]
    )

    dm = apply_entities_canonical_v1(dm)
    extraction = load_critical_signal_json(dm, "legal_canonical_fields_v1")

    assert extraction is not None
    assert _field_by_name(extraction, "Nome_Paciente")["value"] == "MARIA SILVA"
    assert _field_by_name(extraction, "Data_Documento")["normalized_value"] == "2024-03-05"


def test_build_case_outputs_uses_legal_canonical_fields_v1_and_preserves_assertion_levels():
    dm = _dm()
    dm.layer2.sinais_documentais["entities_canonical_v1"] = _signal(
        {
            "document_type": "atestado_medico",
            "document_date": {
                "date_iso": "2024-03-05",
                "literal": "05/03/2024",
                "confidence": 0.97,
                "evidence": {"page": 1, "snippet": "Data: 05/03/2024", "provenance_status": "exact"},
            },
            "internacao": {
                "start": {
                    "date_iso": "2024-03-01",
                    "literal": "01/03/2024",
                    "confidence": 0.96,
                    "evidence": {"page": 1, "snippet": "internado(a) do dia 01/03/2024 ao dia 02/03/2024", "provenance_status": "text_fallback"},
                }
            },
            "afastamento": {
                "estimated_end": {
                    "date_iso": "2024-03-07",
                    "confidence": 0.8,
                    "evidence": {"page": 1, "snippet": "afastado(a) por 5 dia(s)", "provenance_status": "inferred"},
                }
            },
            "quality": {"warnings": []},
        }
    )

    dm = apply_legal_canonical_fields_v1(dm)
    outputs = build_case_outputs([dm])
    facts = {fact["fact_type"]: fact for fact in outputs["timeline_facts"]}

    assert facts["data_documento_medico"]["date_iso"] == "2024-03-05"
    assert facts["data_documento_medico"]["assertion_level"] == "observed"
    assert facts["internacao_inicio"]["assertion_level"] == "observed"
    assert facts["afastamento_fim_estimado"]["date_iso"] == "2024-03-07"
    assert facts["afastamento_fim_estimado"]["assertion_level"] == "estimated"
