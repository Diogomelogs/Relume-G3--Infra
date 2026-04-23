from pathlib import Path

from relluna.services.benchmark import (
    CRITICAL_CLEAN_CASE_IDS,
    CRITICAL_SENTINEL_CASE_IDS,
    evaluate_case,
    evaluate_cases,
    evaluate_semantic_gate,
    load_benchmark_cases,
    render_markdown_report,
)


BENCHMARK_DIR = Path(__file__).parent / "golden"


def test_medical_legal_benchmark_goldens_are_evaluable():
    cases = load_benchmark_cases(BENCHMARK_DIR)
    summary = evaluate_cases(cases)

    assert summary["case_count"] == 11
    assert set(summary["axis_scores"]) == {
        "entidades",
        "eventos",
        "evidencia",
        "confiabilidade",
        "utilidade_juridica",
    }
    assert set(summary["explicit_metrics"]) == {
        "legal_utility_score",
        "evidence_anchor_score",
        "human_review_score",
        "timeline_consistency_score",
    }
    report = render_markdown_report(summary)
    assert "Score por eixo" in report
    assert "Métricas explícitas" in report
    assert "timeline_consistency_score" in report


def test_positive_medical_legal_goldens_score_high():
    cases = {
        case["id"]: case
        for case in load_benchmark_cases(BENCHMARK_DIR)
    }

    for case_id in (
        "001_atestado_afastamento",
        "002_parecer_cid",
        "005_documento_composto",
        "006_paciente_vs_mae",
        "011_evento_estimado_com_explicacao",
    ):
        result = evaluate_case(cases[case_id])
        assert result["overall_score"] >= 90
        assert result["regressions"] == []


def test_birth_date_as_document_date_regression_is_explicit():
    cases = {
        case["id"]: case
        for case in load_benchmark_cases(BENCHMARK_DIR)
    }
    result = evaluate_case(cases["003_regressao_data_nascimento"])

    messages = [item["message"] for item in result["regressions"]]
    assert any("provável data de nascimento" in message for message in messages)
    assert any("Evento obrigatório ausente" in message for message in messages)
    assert result["axis_scores"]["confiabilidade"] < 100


def test_benchmark_penalizes_legally_weak_probatory_event():
    result = evaluate_case(
        {
            "id": "utility_missing_provenance_confidence",
            "actual": {
                "events": [
                    {
                        "event_type": "document_issue_date",
                        "date_iso": "2024-03-05",
                        "title": "Data de emissão",
                        "description": "Data documental extraída.",
                        "entities": {"patient": "MARCOS ANTONIO REIS"},
                        "review_state": "review_recommended",
                        "evidence": {
                            "page": 1,
                            "snippet": "Data 05/03/2024",
                            "bbox": None,
                        },
                    }
                ]
            },
            "expected": {
                "events": [
                    {
                        "event_type": "document_issue_date",
                        "date_iso": "2024-03-05",
                    }
                ],
                "legally_useful_event_types": ["document_issue_date"],
            },
        }
    )

    messages = [item["message"] for item in result["regressions"]]
    assert result["axis_scores"]["utilidade_juridica"] < 100
    assert any("confiança válida" in message for message in messages)
    assert any("status de proveniência jurídico" in message for message in messages)
    assert any("inferido/estimado" in message for message in messages)


def test_benchmark_detects_new_semantic_regressions_explicitly():
    cases = {
        case["id"]: case
        for case in load_benchmark_cases(BENCHMARK_DIR)
    }

    receituario = evaluate_case(cases["004_receituario_vs_atestado"])
    assert any("Tipo documental divergente" in item["message"] for item in receituario["regressions"])

    provider_fp = evaluate_case(cases["007_prestador_falso_positivo"])
    assert any("valor proibido `SAO PAULO`" in item["message"] for item in provider_fp["regressions"])

    cid_espurio = evaluate_case(cases["008_cid_espurio"])
    assert any("valor proibido `ABC12`" in item["message"] for item in cid_espurio["regressions"])

    divergence = evaluate_case(cases["010_divergencia_seed_layer3"])
    assert divergence["timeline_consistency_score"] == 0.0
    assert divergence["explicit_metrics"]["timeline_consistency_score"] == 0.0


def test_semantic_gate_passes_for_current_critical_split():
    summary = evaluate_cases(load_benchmark_cases(BENCHMARK_DIR))

    gate = evaluate_semantic_gate(summary)

    assert gate["ok"] is True
    assert set(gate["checked_clean_cases"]) == set(CRITICAL_CLEAN_CASE_IDS)
    assert set(gate["checked_sentinel_cases"]) == set(CRITICAL_SENTINEL_CASE_IDS)
    assert gate["failures"] == []


def test_semantic_gate_fails_when_clean_case_regresses():
    summary = evaluate_cases(load_benchmark_cases(BENCHMARK_DIR))
    result = next(item for item in summary["results"] if item["case_id"] == "005_documento_composto")
    result["regressions"] = [{"severity": "critical", "message": "regressão simulada"}]

    gate = evaluate_semantic_gate(summary)

    assert gate["ok"] is False
    assert any("critical clean case regressed: 005_documento_composto" in failure for failure in gate["failures"])


def test_semantic_gate_fails_when_sentinel_stops_detecting_regression():
    summary = evaluate_cases(load_benchmark_cases(BENCHMARK_DIR))
    result = next(item for item in summary["results"] if item["case_id"] == "003_regressao_data_nascimento")
    result["regressions"] = []

    gate = evaluate_semantic_gate(summary)

    assert gate["ok"] is False
    assert any(
        "critical sentinel case stopped detecting regressions: 003_regressao_data_nascimento" in failure
        for failure in gate["failures"]
    )
