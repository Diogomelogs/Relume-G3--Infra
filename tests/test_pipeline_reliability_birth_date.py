import json
from pathlib import Path

from relluna.core.document_memory import (
    ArtefatoBruto,
    DocumentMemory,
    Layer1Artefatos,
    OriginType,
)
from relluna.core.document_memory.layer0 import Layer0Custodia
from relluna.core.document_memory.layer1 import ArtefatoTipo, MediaType
from relluna.core.document_memory.layer2 import Layer2Evidence
from relluna.core.document_memory.types_basic import ConfidenceState, ProvenancedString
from relluna.core.normalization import normalize_to_layer4
from relluna.services.context_inference.basic import infer_layer3
from relluna.services.deterministic_extractors.timeline_seed_v2 import seed_timeline_v2
from relluna.services.entities.entities_canonical_v1 import apply_entities_canonical_v1
from relluna.services.benchmark import evaluate_case, load_benchmark_case, project_document_memory


def _dm_with_page_evidence(page_evidence: list[dict]) -> DocumentMemory:
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="birth-date-regression",
            contentfingerprint="0" * 64,
            ingestionagent="pytest",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="artifact-birth-date-regression",
                    tipo=ArtefatoTipo.original,
                    uri="memory://birth-date-regression.pdf",
                )
            ],
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


def _birth_and_issue_page_evidence() -> list[dict]:
    return [
        {
            "page": 1,
            "page_text": (
                "Paciente: MARCOS ANTONIO REIS\n"
                "Data de nascimento: 20/01/1980\n"
                "Data: 05/03/2024\n"
                "CID S83.2\n"
            ),
            "page_taxonomy": {"value": "laudo_medico"},
            "people": {
                "patient_name": "MARCOS ANTONIO REIS",
                "patient_confidence": 0.95,
            },
            "date_candidates": [
                {"literal": "20/01/1980", "date_iso": "1980-01-20"},
                {"literal": "05/03/2024", "date_iso": "2024-03-05"},
            ],
            "anchors": [
                {
                    "label": "date",
                    "value": "1980-01-20",
                    "snippet": "Data de nascimento: 20/01/1980",
                    "bbox": [70, 174, 286, 194],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
                {
                    "label": "date",
                    "value": "2024-03-05",
                    "snippet": "Data: 05/03/2024",
                    "bbox": [70, 210, 220, 230],
                    "source_path": "layer2.sinais_documentais.page_evidence_v1",
                },
            ],
            "clinical_entities": {"cids": ["S83.2"]},
        }
    ]


def test_birth_date_is_not_accepted_as_document_date_in_golden_sentinel():
    case_path = (
        Path(__file__).parent
        / "golden"
        / "003_regressao_data_nascimento"
        / "case.json"
    )
    result = evaluate_case(load_benchmark_case(case_path))

    messages = [regression["message"] for regression in result["regressions"]]

    assert any("provável data de nascimento" in message for message in messages)
    assert any("Evento proibido presente" in message for message in messages)
    assert result["axis_scores"]["confiabilidade"] < 100


def test_entities_canonical_does_not_promote_birth_date_to_document_date():
    dm = _dm_with_page_evidence(_birth_and_issue_page_evidence())

    dm = apply_entities_canonical_v1(dm)
    canonical = json.loads(dm.layer2.sinais_documentais["entities_canonical_v1"].valor)

    assert canonical["document_date"]["date_iso"] == "2024-03-05"
    assert "nascimento" not in canonical["document_date"]["evidence"]["snippet"].lower()


def test_document_issue_date_seed_does_not_use_birth_date():
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="birth-date-seed",
            contentfingerprint="1" * 64,
            ingestionagent="pytest",
        ),
        layer2=Layer2Evidence(),
    )
    dm.layer2.sinais_documentais["entities_canonical_v1"] = ProvenancedString(
        valor=json.dumps(
            {
                "document_type": "laudo_medico",
                "document_date": {
                    "date_iso": "1980-01-20",
                    "literal": "20/01/1980",
                    "confidence": 0.62,
                    "evidence": {
                        "page": 1,
                        "bbox": [70, 174, 286, 194],
                        "snippet": "Data de nascimento: 20/01/1980",
                        "source_path": "layer2.sinais_documentais.page_evidence_v1",
                    },
                },
            },
            ensure_ascii=False,
        ),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )

    dm = seed_timeline_v2(dm)

    assert "timeline_seed_v2" not in dm.layer2.sinais_documentais


def test_layer4_fallback_does_not_promote_birth_date_to_canonical_date():
    dm = _dm_with_page_evidence(_birth_and_issue_page_evidence())

    dm = normalize_to_layer4(dm)

    assert dm.layer4.data_canonica.date().isoformat() == "2024-03-05"


def test_layer4_ignores_poisoned_canonical_document_date_marked_as_birth_date():
    dm = _dm_with_page_evidence(_birth_and_issue_page_evidence())
    dm.layer2.sinais_documentais["entities_canonical_v1"] = ProvenancedString(
        valor=json.dumps(
            {
                "document_type": "laudo_medico",
                "document_date": {
                    "date_iso": "1980-01-20",
                    "literal": "20/01/1980",
                    "confidence": 0.62,
                    "evidence": {
                        "page": 1,
                        "bbox": [70, 174, 286, 194],
                        "snippet": "Data de nascimento: 20/01/1980",
                        "source_path": "layer2.sinais_documentais.page_evidence_v1",
                    },
                },
                "quality": {
                    "warnings": ["document_date_looks_like_birth_date"],
                },
            },
            ensure_ascii=False,
        ),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )

    dm = normalize_to_layer4(dm)

    assert dm.layer4.data_canonica.date().isoformat() == "2024-03-05"


def test_full_pipeline_keeps_birth_date_out_of_document_date_and_timeline():
    page_evidence = _birth_and_issue_page_evidence()
    dm = _dm_with_page_evidence(page_evidence)
    dm.layer2.texto_ocr_literal = ProvenancedString(
        valor="\n".join(item["page_text"] for item in page_evidence),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )

    dm = apply_entities_canonical_v1(dm)
    dm = seed_timeline_v2(dm)
    dm = infer_layer3(dm)
    dm = normalize_to_layer4(dm)

    canonical = json.loads(dm.layer2.sinais_documentais["entities_canonical_v1"].valor)
    seeds = json.loads(dm.layer2.sinais_documentais["timeline_seed_v2"].valor)

    assert canonical["document_date"]["date_iso"] == "2024-03-05"
    assert dm.layer4.data_canonica.date().isoformat() == "2024-03-05"
    assert {(seed["event_hint"], seed["date_iso"]) for seed in seeds} == {
        ("document_issue_date", "2024-03-05")
    }

    events = {(event.event_type, event.date_iso) for event in dm.layer3.eventos_probatorios}
    assert ("document_issue_date", "2024-03-05") in events
    assert ("document_issue_date", "1980-01-20") not in events


def test_benchmark_projection_from_live_pipeline_keeps_birth_date_out_of_actual_payload():
    page_evidence = _birth_and_issue_page_evidence()
    dm = _dm_with_page_evidence(page_evidence)
    dm.layer2.texto_ocr_literal = ProvenancedString(
        valor="\n".join(item["page_text"] for item in page_evidence),
        fonte="pytest",
        metodo="fixture",
        estado=ConfidenceState.confirmado,
        confianca=1.0,
    )

    dm = apply_entities_canonical_v1(dm)
    dm = seed_timeline_v2(dm)
    dm = infer_layer3(dm)
    dm = normalize_to_layer4(dm)

    projected = project_document_memory(dm)

    document_date = projected["entities"]["document_date"]
    assert document_date["date_iso"] == "2024-03-05"
    assert document_date["value"] == "2024-03-05"

    event_pairs = {
        (event["event_type"], event["date_iso"])
        for event in projected["events"]
    }
    assert ("document_issue_date", "2024-03-05") in event_pairs
    assert ("document_issue_date", "1980-01-20") not in event_pairs
