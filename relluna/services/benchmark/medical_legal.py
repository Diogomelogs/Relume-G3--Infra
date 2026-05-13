from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from relluna.services.read_model.timeline_builder import build_timeline_consistency_warning


BENCHMARK_AXES = (
    "entidades",
    "eventos",
    "evidencia",
    "confiabilidade",
    "utilidade_juridica",
)

CRITICAL_CLEAN_CASE_IDS = (
    "001_atestado_afastamento",
    "002_parecer_cid",
    "005_documento_composto",
    "006_paciente_vs_mae",
    "010_divergencia_seed_layer3",
    "011_evento_estimado_com_explicacao",
)

CRITICAL_SENTINEL_CASE_IDS = (
    "003_regressao_data_nascimento",
    "004_receituario_vs_atestado",
    "007_prestador_falso_positivo",
    "008_cid_espurio",
)

CRITICAL_ENTITY_FIELDS = ("patient", "provider", "mother", "cids", "document_date")
OBSERVED_STATUSES = {"observed", "exact", "confirmado", "confirmed"}
INFERRED_STATUSES = {"inferred", "inferido"}
ESTIMATED_STATUSES = {"estimated", "estimado"}
KNOWN_STATUSES = OBSERVED_STATUSES | INFERRED_STATUSES | ESTIMATED_STATUSES


def load_benchmark_case(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_benchmark_cases(directory: str | Path) -> List[Dict[str, Any]]:
    root = Path(directory)
    case_paths = list(root.glob("*.json"))
    case_paths.extend(root.glob("*/case.json"))
    return [load_benchmark_case(path) for path in sorted(case_paths)]


def evaluate_cases(cases: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    results = [evaluate_case(case) for case in cases]
    axis_scores: Dict[str, float] = {}

    for axis in BENCHMARK_AXES:
        if results:
            axis_scores[axis] = round(
                sum(result["axis_scores"][axis] for result in results) / len(results),
                2,
            )
        else:
            axis_scores[axis] = 0.0

    overall = round(sum(axis_scores.values()) / len(BENCHMARK_AXES), 2)
    explicit_metrics = {
        "legal_utility_score": round(
            sum(result["explicit_metrics"]["legal_utility_score"] for result in results) / len(results),
            2,
        ) if results else 0.0,
        "evidence_anchor_score": round(
            sum(result["explicit_metrics"]["evidence_anchor_score"] for result in results) / len(results),
            2,
        ) if results else 0.0,
        "human_review_score": round(
            sum(result["explicit_metrics"]["human_review_score"] for result in results) / len(results),
            2,
        ) if results else 0.0,
        "timeline_consistency_score": round(
            sum(result["explicit_metrics"]["timeline_consistency_score"] for result in results) / len(results),
            2,
        ) if results else 0.0,
    }
    timeline_consistency_score = (
        round(
            sum(result["timeline_consistency_score"] for result in results) / len(results),
            2,
        )
        if results
        else 0.0
    )
    regressions = [
        {
            "case_id": result["case_id"],
            **regression,
        }
        for result in results
        for regression in result["regressions"]
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(results),
        "overall_score": overall,
        "axis_scores": axis_scores,
        "explicit_metrics": explicit_metrics,
        "timeline_consistency_score": timeline_consistency_score,
        "results": results,
        "regressions": regressions,
    }


def evaluate_case(case: Dict[str, Any]) -> Dict[str, Any]:
    actual = deepcopy(case.get("actual") or {})
    expected = deepcopy(case.get("expected") or {})
    regressions: List[Dict[str, str]] = []
    notes: List[str] = []

    axis_scores = {
        "entidades": _score_entities(actual, expected, regressions, notes),
        "eventos": _score_events(actual, expected, regressions, notes),
        "evidencia": _score_evidence(actual, expected, regressions, notes),
        "confiabilidade": _score_reliability(actual, expected, regressions, notes),
        "utilidade_juridica": _score_legal_utility(actual, expected, regressions, notes),
    }
    overall = round(sum(axis_scores.values()) / len(axis_scores), 2)
    timeline_consistency_score = _timeline_consistency_score(actual)
    explicit_metrics = {
        "legal_utility_score": axis_scores["utilidade_juridica"],
        "evidence_anchor_score": axis_scores["evidencia"],
        "human_review_score": _human_review_score(actual, expected, regressions, notes),
        "timeline_consistency_score": timeline_consistency_score,
    }

    return {
        "case_id": case.get("id"),
        "title": case.get("title"),
        "overall_score": overall,
        "axis_scores": axis_scores,
        "explicit_metrics": explicit_metrics,
        "timeline_consistency_score": timeline_consistency_score,
        "regressions": regressions,
        "notes": notes,
    }


def project_document_memory(dm: Any) -> Dict[str, Any]:
    """Project a DocumentMemory-like object into the benchmark DTO.

    The projection is intentionally read-only and tolerant of dicts/Pydantic
    models because persisted documents and tests currently use both shapes.
    """
    canonical = _load_dm_signal(dm, "entities_canonical_v1") or {}
    timeline = _extract_events_from_dm(dm)
    quality = canonical.get("quality") if isinstance(canonical, dict) else {}
    consistency_warning = build_timeline_consistency_warning(dm)

    entities = {
        "patient": _entity_from_canonical(canonical, "patient"),
        "provider": _entity_from_canonical(canonical, "provider"),
        "mother": _entity_from_canonical(canonical, "mother"),
        "document_date": _date_entity_from_canonical(canonical),
        "cids": _cid_entities_from_canonical(canonical),
    }

    return {
        "entities": entities,
        "events": timeline,
        "warnings": list((quality or {}).get("warnings") or []),
        "timeline_consistency": {
            "score": 0.0 if consistency_warning else 100.0,
            "warning": consistency_warning,
        },
        "document_type": canonical.get("document_type") if isinstance(canonical, dict) else None,
    }


def render_markdown_report(summary: Dict[str, Any]) -> str:
    lines = [
        "# Benchmark medico-juridico auditavel",
        "",
        f"Gerado em: `{summary.get('generated_at')}`",
        f"Casos avaliados: **{summary.get('case_count', 0)}**",
        f"Score geral: **{summary.get('overall_score', 0):.2f}/100**",
        "",
        "## Score por eixo",
        "",
        "| Eixo | Score |",
        "| --- | ---: |",
    ]

    for axis in BENCHMARK_AXES:
        lines.append(f"| {axis} | {summary['axis_scores'].get(axis, 0):.2f} |")

    lines.extend(
        [
            "",
            "## Métricas explícitas",
            "",
            "| Métrica | Score |",
            "| --- | ---: |",
            f"| utilidade_juridica | {summary.get('explicit_metrics', {}).get('legal_utility_score', 0):.2f} |",
            f"| ancoragem_evidencia | {summary.get('explicit_metrics', {}).get('evidence_anchor_score', 0):.2f} |",
            f"| revisao_humana | {summary.get('explicit_metrics', {}).get('human_review_score', 0):.2f} |",
            f"| consistencia_timeline | {summary.get('explicit_metrics', {}).get('timeline_consistency_score', 0):.2f} |",
        ]
    )

    lines.extend(["", "## Casos", "", "| Caso | Score | Entidades | Eventos | Evidencia | Confiabilidade | Utilidade juridica | Regressões |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])

    for result in summary.get("results", []):
        axes = result["axis_scores"]
        lines.append(
            "| {case} | {overall:.2f} | {ent:.2f} | {evt:.2f} | {evi:.2f} | {conf:.2f} | {jur:.2f} | {reg} |".format(
                case=result.get("case_id"),
                overall=result.get("overall_score", 0),
                ent=axes.get("entidades", 0),
                evt=axes.get("eventos", 0),
                evi=axes.get("evidencia", 0),
                conf=axes.get("confiabilidade", 0),
                jur=axes.get("utilidade_juridica", 0),
                reg=len(result.get("regressions") or []),
            )
        )

    consistency_scores = [
        result.get("timeline_consistency_score")
        for result in summary.get("results", [])
        if result.get("timeline_consistency_score") is not None
    ]
    consistency_score = (
        round(sum(consistency_scores) / len(consistency_scores), 2)
        if consistency_scores
        else 0.0
    )
    lines.extend(
        [
            "",
            "## Métrica de consistência",
            "",
            f"- timeline_consistency_score: **{consistency_score:.2f}/100**",
        ]
    )

    lines.extend(["", "## Regressões explícitas", ""])
    regressions = summary.get("regressions") or []
    if not regressions:
        lines.append("Nenhuma regressão detectada nos casos avaliados.")
    else:
        for regression in regressions:
            lines.append(
                "- `{case_id}` [{severity}] {axis}: {message}".format(
                    case_id=regression.get("case_id"),
                    severity=regression.get("severity", "warning"),
                    axis=regression.get("axis", "geral"),
                    message=regression.get("message", ""),
                )
            )

    lines.extend(
        [
            "",
            "## Estrutura proposta",
            "",
            "- Entidades: paciente, prestador, mãe, CID e data documental como campos críticos, com valor esperado e lastro.",
            "- Eventos: timeline com tipos jurídicos úteis, data, título, descrição, entidades vinculadas e estado observado/inferido/estimado.",
            "- Evidência: cada entidade/evento relevante deve apontar página, snippet, bbox e caminho lógico da fonte.",
            "- Confiabilidade: distinção explícita entre observado, inferido e estimado, confiança numérica e revisão humana quando necessário.",
            "- Utilidade jurídica: penaliza eventos sem descrição, sem entidades críticas, sem estado de revisão ou sem relevância para advogado.",
        ]
    )

    return "\n".join(lines) + "\n"


def evaluate_semantic_gate(
    summary: Dict[str, Any],
    *,
    clean_case_ids: Iterable[str] = CRITICAL_CLEAN_CASE_IDS,
    sentinel_case_ids: Iterable[str] = CRITICAL_SENTINEL_CASE_IDS,
    min_clean_score: float = 90.0,
) -> Dict[str, Any]:
    results_by_id = {
        result.get("case_id"): result
        for result in (summary.get("results") or [])
        if isinstance(result, dict) and result.get("case_id")
    }

    failures: List[str] = []
    checked_clean_cases: List[str] = []
    checked_sentinel_cases: List[str] = []

    for case_id in clean_case_ids:
        result = results_by_id.get(case_id)
        if result is None:
            failures.append(f"critical clean case missing from benchmark: {case_id}")
            continue
        checked_clean_cases.append(case_id)
        if result.get("regressions"):
            failures.append(
                f"critical clean case regressed: {case_id} has {len(result['regressions'])} regression(s)"
            )
        if float(result.get("overall_score") or 0.0) < min_clean_score:
            failures.append(
                f"critical clean case below minimum score: {case_id} scored {float(result.get('overall_score') or 0.0):.2f} < {min_clean_score:.2f}"
            )

    for case_id in sentinel_case_ids:
        result = results_by_id.get(case_id)
        if result is None:
            failures.append(f"critical sentinel case missing from benchmark: {case_id}")
            continue
        checked_sentinel_cases.append(case_id)
        if not result.get("regressions"):
            failures.append(f"critical sentinel case stopped detecting regressions: {case_id}")

    return {
        "ok": not failures,
        "failures": failures,
        "checked_clean_cases": checked_clean_cases,
        "checked_sentinel_cases": checked_sentinel_cases,
        "min_clean_score": min_clean_score,
    }


def _score_entities(
    actual: Dict[str, Any],
    expected: Dict[str, Any],
    regressions: List[Dict[str, str]],
    notes: List[str],
) -> float:
    expected_entities = expected.get("entities") or {}
    actual_entities = actual.get("entities") or {}
    checks: List[bool] = []

    expected_document_type = expected.get("document_type")
    if expected_document_type is not None:
        ok = _normalize_value(actual.get("document_type")) == _normalize_value(expected_document_type)
        checks.append(ok)
        if not ok:
            regressions.append(
                _regression(
                    "entidades",
                    "critical",
                    f"Tipo documental divergente: esperado `{expected_document_type}`.",
                )
            )

    for field in CRITICAL_ENTITY_FIELDS:
        if field not in expected_entities:
            continue

        expected_value = expected_entities[field]
        actual_value = actual_entities.get(field)
        ok = _entity_matches(actual_value, expected_value)
        checks.append(ok)
        if not ok:
            regressions.append(
                _regression(
                    "entidades",
                    "critical",
                    f"Campo crítico `{field}` divergente: esperado `{expected_value}`.",
                )
            )

    forbidden_entities = expected.get("forbidden_entities") or {}
    for field, forbidden_values in forbidden_entities.items():
        actual_value = actual_entities.get(field)
        actual_values = {_normalize_value(v) for v in _entity_values(actual_value)}
        for forbidden_value in forbidden_values or []:
            ok = _normalize_value(forbidden_value) not in actual_values
            checks.append(ok)
            if not ok:
                regressions.append(
                    _regression(
                        "entidades",
                        "critical",
                        f"Campo `{field}` contém valor proibido `{forbidden_value}`.",
                    )
                )

    if not checks:
        notes.append("Sem entidades críticas esperadas para pontuar.")
        return 0.0

    return round(100.0 * sum(1 for ok in checks if ok) / len(checks), 2)


def _score_events(
    actual: Dict[str, Any],
    expected: Dict[str, Any],
    regressions: List[Dict[str, str]],
    notes: List[str],
) -> float:
    actual_events = actual.get("events") or []
    required = expected.get("events") or []
    forbidden = expected.get("forbidden_events") or []
    checks: List[bool] = []

    for event in required:
        ok = _find_event(actual_events, event) is not None
        checks.append(ok)
        if not ok:
            regressions.append(
                _regression(
                    "eventos",
                    "critical",
                    f"Evento obrigatório ausente: `{event.get('event_type')}` em `{event.get('date_iso')}`.",
                )
            )

    for event in forbidden:
        ok = _find_event(actual_events, event) is None
        checks.append(ok)
        if not ok:
            regressions.append(
                _regression(
                    "eventos",
                    "critical",
                    f"Evento proibido presente: `{event.get('event_type')}` em `{event.get('date_iso')}`.",
                )
            )

    if not checks:
        notes.append("Sem eventos obrigatórios/proibidos para pontuar.")
        return 0.0

    return round(100.0 * sum(1 for ok in checks if ok) / len(checks), 2)


def _score_evidence(
    actual: Dict[str, Any],
    expected: Dict[str, Any],
    regressions: List[Dict[str, str]],
    notes: List[str],
) -> float:
    anchors = _collect_required_anchors(actual, expected)
    if not anchors:
        notes.append("Sem lastros exigidos para pontuar evidência.")
        return 0.0

    complete = 0
    for label, evidence in anchors:
        if _has_complete_evidence(evidence):
            complete += 1
        else:
            regressions.append(
                _regression(
                    "evidencia",
                    "major",
                    f"Lastro incompleto para `{label}`; exige página, snippet e bbox.",
                )
            )

    return round(100.0 * complete / len(anchors), 2)


def _score_reliability(
    actual: Dict[str, Any],
    expected: Dict[str, Any],
    regressions: List[Dict[str, str]],
    notes: List[str],
) -> float:
    checks: List[bool] = []
    actual_entities = actual.get("entities") or {}
    actual_events = actual.get("events") or []

    forbidden_dates = set(expected.get("forbidden_document_dates") or [])
    document_date = actual_entities.get("document_date")
    document_date_value = _entity_value(document_date)
    if forbidden_dates:
        ok = document_date_value not in forbidden_dates
        checks.append(ok)
        if not ok:
            regressions.append(
                _regression(
                    "confiabilidade",
                    "critical",
                    f"Data documental usa data proibida `{document_date_value}`, provável data de nascimento.",
                )
            )

    for label, item in _iter_scored_items(actual):
        status = _provenance_status(item)
        confidence = _confidence(item)
        status_ok = status in KNOWN_STATUSES
        confidence_ok = confidence is None or 0.0 <= confidence <= 1.0
        checks.extend([status_ok, confidence_ok])
        if not status_ok:
            regressions.append(
                _regression(
                    "confiabilidade",
                    "major",
                    f"`{label}` não distingue observado/inferido/estimado.",
                )
            )
        if not confidence_ok:
            regressions.append(
                _regression(
                    "confiabilidade",
                    "major",
                    f"`{label}` tem confiança fora de 0..1.",
                )
            )

    for event in actual_events:
        event_type = event.get("event_type")
        status = _provenance_status(event)
        if event_type and "estimado" in event_type and status not in ESTIMATED_STATUSES:
            checks.append(False)
            regressions.append(
                _regression(
                    "confiabilidade",
                    "critical",
                    f"Evento estimado `{event_type}` não está marcado como estimado.",
                )
            )

    if not checks:
        notes.append("Sem itens confiáveis para pontuar.")
        return 0.0

    return round(100.0 * sum(1 for ok in checks if ok) / len(checks), 2)


def _score_legal_utility(
    actual: Dict[str, Any],
    expected: Dict[str, Any],
    regressions: List[Dict[str, str]],
    notes: List[str],
) -> float:
    actual_events = actual.get("events") or []
    useful_types = set(expected.get("legally_useful_event_types") or [])
    required_events = expected.get("events") or []
    checks: List[bool] = []

    for requirement in required_events:
        event = _find_event(actual_events, requirement)
        if not event:
            checks.append(False)
            continue

        entities = event.get("entities") or {}
        event_status = _provenance_status(event)
        event_confidence = _confidence(event)
        evidence = event.get("evidence") or _first_citation(event)
        has_exact_evidence = _has_complete_evidence(evidence)
        provenance_ok = event_status in KNOWN_STATUSES
        confidence_ok = event_confidence is not None and 0.0 <= event_confidence <= 1.0
        non_exact_marked = has_exact_evidence or event_status in (
            INFERRED_STATUSES | ESTIMATED_STATUSES
        )

        checks.extend(
            [
                bool(event.get("title")),
                bool(event.get("description")),
                bool(event.get("review_state")),
                confidence_ok,
                provenance_ok,
                non_exact_marked,
                event.get("event_type") in useful_types if useful_types else True,
                bool(entities.get("patient")),
            ]
        )

        if not event.get("description"):
            regressions.append(
                _regression(
                    "utilidade_juridica",
                    "major",
                    f"Evento `{event.get('event_type')}` não tem descrição útil para advogado.",
                )
            )
        if not confidence_ok:
            regressions.append(
                _regression(
                    "utilidade_juridica",
                    "major",
                    f"Evento `{event.get('event_type')}` não tem confiança válida.",
                )
            )
        if not provenance_ok:
            regressions.append(
                _regression(
                    "utilidade_juridica",
                    "major",
                    f"Evento `{event.get('event_type')}` não tem status de proveniência jurídico.",
                )
            )
        if not non_exact_marked:
            regressions.append(
                _regression(
                    "utilidade_juridica",
                    "major",
                    f"Evento `{event.get('event_type')}` sem evidência exata não foi marcado como inferido/estimado.",
                )
            )

    if not checks:
        notes.append("Sem eventos avaliáveis para utilidade jurídica.")
        return 0.0

    return round(100.0 * sum(1 for ok in checks if ok) / len(checks), 2)


def _timeline_consistency_score(actual: Dict[str, Any]) -> float:
    explicit_score = actual.get("timeline_consistency_score")
    if explicit_score is not None:
        return _bounded_score(explicit_score)

    consistency = actual.get("timeline_consistency")
    if isinstance(consistency, dict) and consistency.get("score") is not None:
        return _bounded_score(consistency.get("score"))

    for warning in actual.get("warnings") or []:
        if isinstance(warning, dict) and warning.get("code") == "timeline_seed_v2_layer3_divergence":
            return 0.0

    return 100.0


def _human_review_score(
    actual: Dict[str, Any],
    expected: Dict[str, Any],
    regressions: List[Dict[str, str]],
    notes: List[str],
) -> float:
    del expected
    checks: List[bool] = []
    review_items = actual.get("review_items") or []

    for label, item in _iter_scored_items(actual):
        status = _provenance_status(item)
        review_state = item.get("review_state")
        if status in (INFERRED_STATUSES | ESTIMATED_STATUSES) or review_state in {"needs_review", "review_recommended"}:
            ok = bool(review_state)
            checks.append(ok)
            if not ok:
                regressions.append(
                    _regression(
                        "confiabilidade",
                        "major",
                        f"`{label}` exige revisão humana, mas não expõe review_state.",
                    )
                )

    if any(_provenance_status(event) in (INFERRED_STATUSES | ESTIMATED_STATUSES) for event in (actual.get("events") or [])):
        review_items_ok = bool(review_items)
        checks.append(review_items_ok)
        if not review_items_ok:
            regressions.append(
                _regression(
                    "utilidade_juridica",
                    "major",
                    "Caso com itens inferidos/estimados não expõe fila de revisão humana.",
                )
            )

    if not checks:
        notes.append("Sem itens que exijam revisão humana para pontuar.")
        return 100.0

    return round(100.0 * sum(1 for ok in checks if ok) / len(checks), 2)


def _bounded_score(value: Any) -> float:
    try:
        return round(max(0.0, min(100.0, float(value))), 2)
    except (TypeError, ValueError):
        return 0.0


def _entity_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        actual_values = {_normalize_value(v) for v in _entity_values(actual)}
        return all(_normalize_value(v) in actual_values for v in expected)
    return _normalize_value(_entity_value(actual)) == _normalize_value(expected)


def _entity_value(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("value") or value.get("date_iso") or value.get("code")
    return value


def _entity_values(value: Any) -> List[Any]:
    if isinstance(value, list):
        return [_entity_value(item) for item in value]
    return [_entity_value(value)]


def _normalize_value(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().upper().split())


def _find_event(events: List[Dict[str, Any]], requirement: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for event in events:
        if requirement.get("event_type") and event.get("event_type") != requirement.get("event_type"):
            continue
        if requirement.get("date_iso") and event.get("date_iso") != requirement.get("date_iso"):
            continue
        return event
    return None


def _collect_required_anchors(actual: Dict[str, Any], expected: Dict[str, Any]) -> List[Tuple[str, Any]]:
    anchors: List[Tuple[str, Any]] = []
    actual_entities = actual.get("entities") or {}

    for field in CRITICAL_ENTITY_FIELDS:
        if field not in (expected.get("entities") or {}):
            continue
        value = actual_entities.get(field)
        if isinstance(value, list):
            anchors.extend((f"entity:{field}", item.get("evidence")) for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            anchors.append((f"entity:{field}", value.get("evidence")))

    for requirement in expected.get("events") or []:
        event = _find_event(actual.get("events") or [], requirement)
        if event:
            anchors.append((f"event:{event.get('event_type')}", event.get("evidence") or _first_citation(event)))

    return anchors


def _has_complete_evidence(evidence: Any) -> bool:
    if not isinstance(evidence, dict):
        return False
    return (
        evidence.get("page") is not None
        and bool(evidence.get("snippet"))
        and isinstance(evidence.get("bbox"), list)
        and len(evidence.get("bbox") or []) == 4
    )


def _first_citation(event: Dict[str, Any]) -> Any:
    citations = event.get("citations") or []
    return citations[0] if citations else None


def _iter_scored_items(actual: Dict[str, Any]) -> Iterable[Tuple[str, Dict[str, Any]]]:
    entities = actual.get("entities") or {}
    for field, value in entities.items():
        if isinstance(value, list):
            for idx, item in enumerate(value):
                if isinstance(item, dict):
                    yield f"entity:{field}:{idx}", item
        elif isinstance(value, dict):
            yield f"entity:{field}", value

    for idx, event in enumerate(actual.get("events") or []):
        if isinstance(event, dict):
            yield f"event:{idx}:{event.get('event_type')}", event


def _provenance_status(item: Dict[str, Any]) -> Optional[str]:
    status = item.get("provenance_status") or item.get("status")
    if status is None and item.get("evidence"):
        status = item["evidence"].get("provenance_status")
    return str(status).strip().lower() if status is not None else None


def _confidence(item: Dict[str, Any]) -> Optional[float]:
    confidence = item.get("confidence")
    if confidence is None and item.get("evidence"):
        confidence = item["evidence"].get("confidence")
    if confidence is None:
        return None
    try:
        return float(confidence)
    except (TypeError, ValueError):
        return -1.0


def _regression(axis: str, severity: str, message: str) -> Dict[str, str]:
    return {"axis": axis, "severity": severity, "message": message}


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _load_dm_signal(dm: Any, key: str) -> Optional[Any]:
    layer2 = _get(dm, "layer2")
    sinais = _get(layer2, "sinais_documentais", {}) or {}
    signal = sinais.get(key)
    value = _get(signal, "valor", signal)
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _entity_from_canonical(canonical: Dict[str, Any], field: str) -> Optional[Dict[str, Any]]:
    block = canonical.get(field) or {}
    if not block.get("name"):
        return None
    return {
        "value": block.get("name"),
        "provenance_status": block.get("provenance_status") or "inferred",
        "confidence": block.get("confidence"),
        "evidence": block.get("evidence"),
    }


def _date_entity_from_canonical(canonical: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    block = canonical.get("document_date") or {}
    date_iso = block.get("date_iso")
    if not date_iso:
        return None
    return {
        "value": date_iso,
        "date_iso": date_iso,
        "provenance_status": block.get("provenance_status") or "inferred",
        "confidence": block.get("confidence"),
        "evidence": block.get("evidence"),
    }


def _cid_entities_from_canonical(canonical: Dict[str, Any]) -> List[Dict[str, Any]]:
    clinical = canonical.get("clinical") or {}
    cids = []
    for item in clinical.get("cids") or []:
        if not isinstance(item, dict) or not item.get("code"):
            continue
        cids.append(
            {
                "value": item.get("code"),
                "code": item.get("code"),
                "provenance_status": item.get("provenance_status") or "observed",
                "confidence": item.get("confidence"),
                "evidence": item.get("evidence"),
            }
        )
    return cids


def _extract_events_from_dm(dm: Any) -> List[Dict[str, Any]]:
    layer3 = _get(dm, "layer3")
    events = _get(layer3, "eventos_probatorios", []) or []
    projected: List[Dict[str, Any]] = []

    for event in events:
        citations = [_model_to_dict(c) for c in (_get(event, "citations", []) or [])]
        projected.append(
            {
                "event_id": _get(event, "event_id"),
                "event_type": _get(event, "event_type"),
                "title": _get(event, "title"),
                "description": _get(event, "description"),
                "date_iso": _get(event, "date_iso"),
                "entities": _get(event, "entities", {}) or {},
                "citations": citations,
                "evidence": citations[0] if citations else None,
                "confidence": _get(event, "confidence"),
                "review_state": _get(event, "review_state"),
                "provenance_status": _get(event, "provenance_status"),
            }
        )

    return projected


def _model_to_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {}
