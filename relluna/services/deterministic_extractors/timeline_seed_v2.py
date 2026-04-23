from __future__ import annotations

from hashlib import sha256
from typing import Any, Dict, List, Optional

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.types_basic import ProvenancedString
from relluna.services.evidence.signals import dump_critical_signal_json, load_critical_signal_json

FONTE = "deterministic_extractors.timeline_seed_v2"

_EVENT_PRIORITY: Dict[str, int] = {
    "internacao_inicio": 10,
    "internacao_fim": 20,
    "document_issue_date": 40,
    "parecer_emitido": 45,
    "encaminhamento_clinico": 50,
    "registro_condicao_clinica": 55,
    "afastamento_inicio": 60,
    "afastamento_fim_estimado": 70,
    "birth_date": 999,
    "document_date_candidate": 900,
}

_INCLUDE_IN_TIMELINE: Dict[str, bool] = {
    "internacao_inicio": True,
    "internacao_fim": True,
    "document_issue_date": True,
    "parecer_emitido": True,
    "encaminhamento_clinico": True,
    "registro_condicao_clinica": True,
    "afastamento_inicio": True,
    "afastamento_fim_estimado": True,
    "birth_date": False,
    "document_date_candidate": False,
}

_BIRTH_DATE_MARKERS = (
    "nascimento",
    "nascto",
    "data de nascimento",
    "idade",
)


def _load_signal_json(dm: DocumentMemory, key: str) -> Any:
    return load_critical_signal_json(dm, key)


def _review_state(conf: float) -> str:
    if conf >= 0.95:
        return "auto_confirmed"
    if conf >= 0.80:
        return "review_recommended"
    return "needs_review"


def _make_seed(
    *,
    date_iso: str,
    event_hint: str,
    date_literal: Optional[str],
    page: Optional[int],
    bbox: Optional[List[float]],
    snippet: Optional[str],
    source: str,
    source_path: str,
    confidence: float,
    subdoc_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    basis = f"{date_iso}|{event_hint}|{page}|{subdoc_id or ''}|{snippet or date_literal or ''}|{source_path}"
    seed_id = sha256(basis.encode("utf-8")).hexdigest()[:16]

    payload: Dict[str, Any] = {
        "seed_id": seed_id,
        "date_iso": date_iso,
        "date_literal": date_literal,
        "event_hint": event_hint,
        "include_in_timeline": _INCLUDE_IN_TIMELINE.get(event_hint, False),
        "page": page,
        "bbox": bbox,
        "snippet": snippet or date_literal,
        "source": source,
        "source_path": source_path,
        "confidence": confidence,
        "review_state": _review_state(confidence),
        "provenance_status": "exact" if bbox else "inferred",
        "priority": _EVENT_PRIORITY.get(event_hint, 500),
    }

    if subdoc_id is not None:
        payload["subdoc_id"] = subdoc_id

    if extra:
        payload.update(extra)

    return payload


def _dedup(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()

    for item in items:
        key = (
            item.get("date_iso"),
            item.get("event_hint"),
            item.get("subdoc_id"),
            item.get("page"),
            item.get("snippet"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)

    out.sort(key=lambda x: (x["date_iso"], x.get("priority", 500), x["seed_id"]))
    return out


def _looks_like_birth_date_evidence(evidence: Dict[str, Any], literal: Optional[str]) -> bool:
    snippet = str((evidence or {}).get("snippet") or literal or "").lower()
    return any(marker in snippet for marker in _BIRTH_DATE_MARKERS)


def _assertion_level_from_evidence(evidence: Dict[str, Any]) -> str:
    provenance = str((evidence or {}).get("provenance_status") or "").lower()
    if (evidence or {}).get("bbox") and provenance == "exact":
        return "observed"
    if provenance in {"inferred", "estimated", "text_fallback", "snippet_only"}:
        return "inferred"
    return "unknown"


def _build_from_segment_unit(
    unit: Dict[str, Any],
    *,
    source_signal: str,
) -> List[Dict[str, Any]]:
    seeds: List[Dict[str, Any]] = []
    subdoc_id = unit.get("subdoc_id")
    page = unit.get("page_index")
    if page is None:
        pages = unit.get("pages") or []
        page = pages[0] if pages else None

    document_type = unit.get("document_type")
    provider = unit.get("provider") or {}
    document_date = unit.get("document_date") or {}
    clinical = unit.get("clinical") or {}
    source_path = f"layer2.sinais_documentais.{source_signal}"

    if document_type == "atestado_medico":
        for event_hint, block_name, key_name, conf_default in [
            ("internacao_inicio", "internacao", "start", 0.96),
            ("internacao_fim", "internacao", "end", 0.96),
            ("afastamento_inicio", "afastamento", "start", 0.90),
            ("afastamento_fim_estimado", "afastamento", "estimated_end", 0.80),
        ]:
            block = unit.get(block_name) or {}
            item = block.get(key_name) or {}
            if not item.get("date_iso"):
                continue
            evidence = item.get("evidence") or {}
            seeds.append(
                _make_seed(
                    date_iso=item["date_iso"],
                    event_hint=event_hint,
                    date_literal=item.get("literal"),
                    page=evidence.get("page", page),
                    bbox=evidence.get("bbox"),
                    snippet=evidence.get("snippet"),
                    source=source_signal,
                    source_path=source_path,
                    confidence=float(item.get("confidence") or conf_default),
                    subdoc_id=subdoc_id,
                    extra={
                        "document_type": document_type,
                        "provider_name": provider.get("name"),
                        "assertion_level": (
                            "inferred" if event_hint == "afastamento_fim_estimado" else _assertion_level_from_evidence(evidence)
                        ),
                        "warnings": unit.get("warnings") or [],
                        "uncertainties": unit.get("uncertainties") or [],
                        "duration_days": (unit.get("afastamento") or {}).get("duration_days", {}).get("value"),
                    },
                )
            )

        if seeds:
            return _dedup(seeds)

    document_date_evidence = document_date.get("evidence") or {}
    if document_date.get("date_iso") and not _looks_like_birth_date_evidence(document_date_evidence, document_date.get("literal")):
        hint = "parecer_emitido" if document_type == "parecer_medico" else "document_issue_date"
        seeds.append(
            _make_seed(
                date_iso=document_date["date_iso"],
                event_hint=hint,
                date_literal=document_date.get("literal"),
                page=document_date_evidence.get("page", page),
                bbox=document_date_evidence.get("bbox"),
                snippet=document_date_evidence.get("snippet"),
                source=source_signal,
                source_path=source_path,
                confidence=float(document_date.get("confidence") or 0.84),
                subdoc_id=subdoc_id,
                extra={
                    "document_type": document_type,
                    "provider_name": provider.get("name"),
                    "assertion_level": document_date.get("assertion_level") or _assertion_level_from_evidence(document_date_evidence),
                    "warnings": unit.get("warnings") or [],
                    "uncertainties": unit.get("uncertainties") or [],
                },
            )
        )

    if (
        document_type == "parecer_medico"
        and clinical.get("cids")
        and document_date.get("date_iso")
        and not _looks_like_birth_date_evidence(document_date_evidence, document_date.get("literal"))
    ):
        cid_codes = [
            item.get("code")
            for item in clinical.get("cids")
            if isinstance(item, dict) and item.get("code")
        ]
        seeds.append(
            _make_seed(
                date_iso=document_date["date_iso"],
                event_hint="registro_condicao_clinica",
                date_literal=document_date.get("literal"),
                page=document_date_evidence.get("page", page),
                bbox=document_date_evidence.get("bbox"),
                snippet=", ".join(cid_codes),
                source=source_signal,
                source_path=source_path,
                confidence=0.92,
                subdoc_id=subdoc_id,
                extra={
                    "document_type": document_type,
                    "cids": cid_codes,
                    "provider_name": provider.get("name"),
                    "assertion_level": "observed" if any((item.get("evidence") or {}).get("bbox") for item in clinical.get("cids") or []) else "inferred",
                    "warnings": unit.get("warnings") or [],
                    "uncertainties": unit.get("uncertainties") or [],
                },
            )
        )

    return _dedup(seeds)


def _build_from_entities_canonical(
    dm: DocumentMemory,
    canonical: Dict[str, Any],
) -> List[Dict[str, Any]]:
    seeds: List[Dict[str, Any]] = []
    subdoc_id = canonical.get("subdoc_id")

    document_type = canonical.get("document_type")
    provider = canonical.get("provider") or {}
    document_date = canonical.get("document_date") or {}
    clinical = canonical.get("clinical") or {}

    # PRIORIDADE MÁXIMA: atestado médico deve virar eventos clínicos reais
    if document_type == "atestado_medico":
        internacao = canonical.get("internacao") or {}
        afastamento = canonical.get("afastamento") or {}

        for event_hint, block_name, key_name, conf_default in [
            ("internacao_inicio", "internacao", "start", 0.96),
            ("internacao_fim", "internacao", "end", 0.96),
            ("afastamento_inicio", "afastamento", "start", 0.90),
            ("afastamento_fim_estimado", "afastamento", "estimated_end", 0.80),
        ]:
            block = canonical.get(block_name) or {}
            item = block.get(key_name) or {}

            if item.get("date_iso"):
                ev = item.get("evidence") or {}

                extra = {
                    "document_type": document_type,
                    "provider_name": provider.get("name"),
                }

                if block_name == "afastamento":
                    extra["duration_days"] = (afastamento.get("duration_days") or {}).get("value")

                seeds.append(
                    _make_seed(
                        date_iso=item["date_iso"],
                        event_hint=event_hint,
                        date_literal=item.get("literal"),
                        page=ev.get("page"),
                        bbox=ev.get("bbox"),
                        snippet=ev.get("snippet"),
                        source="entities_canonical_v1",
                        source_path="layer2.sinais_documentais.entities_canonical_v1",
                        confidence=float(item.get("confidence") or conf_default),
                        subdoc_id=subdoc_id,
                        extra=extra,
                    )
                )

        # se já conseguiu eventos clínicos, não cair para emissão genérica
        if seeds:
            return _dedup(seeds)

    # parecer/documento: fallback documental
    document_date_evidence = document_date.get("evidence") or {}
    document_date_looks_like_birth_date = _looks_like_birth_date_evidence(
        document_date_evidence,
        document_date.get("literal"),
    )

    if document_date.get("date_iso") and not document_date_looks_like_birth_date:
        ev = document_date_evidence
        hint = "parecer_emitido" if document_type == "parecer_medico" else "document_issue_date"

        seeds.append(
            _make_seed(
                date_iso=document_date["date_iso"],
                event_hint=hint,
                date_literal=document_date.get("literal"),
                page=ev.get("page"),
                bbox=ev.get("bbox"),
                snippet=ev.get("snippet"),
                source="entities_canonical_v1",
                source_path="layer2.sinais_documentais.entities_canonical_v1",
                confidence=float(document_date.get("confidence") or 0.84),
                subdoc_id=subdoc_id,
                extra={
                    "document_type": document_type,
                    "provider_name": provider.get("name"),
                },
            )
        )

    # parecer médico: condição clínica
    if (
        document_type == "parecer_medico"
        and clinical.get("cids")
        and document_date.get("date_iso")
        and not document_date_looks_like_birth_date
    ):
        cid_codes = [
            c.get("code")
            for c in clinical.get("cids")
            if isinstance(c, dict) and c.get("code")
        ]

        seeds.append(
            _make_seed(
                date_iso=document_date["date_iso"],
                event_hint="registro_condicao_clinica",
                date_literal=document_date.get("literal"),
                page=document_date.get("evidence", {}).get("page"),
                bbox=document_date.get("evidence", {}).get("bbox"),
                snippet=", ".join(cid_codes),
                source="entities_canonical_v1",
                source_path="layer2.sinais_documentais.entities_canonical_v1",
                confidence=0.92,
                subdoc_id=subdoc_id,
                extra={
                    "document_type": document_type,
                    "cids": cid_codes,
                    "provider_name": provider.get("name"),
                },
            )
        )

    return _dedup(seeds)


def build_timeline_seeds_v2(dm: DocumentMemory) -> List[Dict[str, Any]]:
    subdocument_units = _load_signal_json(dm, "subdocument_unit_v1") or []
    if isinstance(subdocument_units, list) and subdocument_units:
        seeds: List[Dict[str, Any]] = []
        for unit in subdocument_units:
            if not isinstance(unit, dict):
                continue
            seeds.extend(_build_from_segment_unit(unit, source_signal="subdocument_unit_v1"))
        if seeds:
            return _dedup(seeds)

    page_units = _load_signal_json(dm, "page_unit_v1") or []
    if isinstance(page_units, list) and page_units:
        seeds = []
        for unit in page_units:
            if not isinstance(unit, dict):
                continue
            seeds.extend(_build_from_segment_unit(unit, source_signal="page_unit_v1"))
        if seeds:
            return _dedup(seeds)

    canonical = _load_signal_json(dm, "entities_canonical_v1")

    if isinstance(canonical, dict):
        subdocs = canonical.get("subdocuments") or []
        if isinstance(subdocs, list) and subdocs:
            seeds: List[Dict[str, Any]] = []
            for subdoc in subdocs:
                if not isinstance(subdoc, dict):
                    continue
                seeds.extend(_build_from_entities_canonical(dm, subdoc))
            if seeds:
                return _dedup(seeds)
        return _build_from_entities_canonical(dm, canonical)

    return []


def seed_timeline_v2(dm: DocumentMemory) -> DocumentMemory:
    if dm.layer2 is None:
        return dm

    seeds = build_timeline_seeds_v2(dm)
    if not seeds:
        return dm

    dm.layer2.sinais_documentais["timeline_seed_v2"] = ProvenancedString(
        valor=dump_critical_signal_json("timeline_seed_v2", seeds, dm=dm),
        fonte=FONTE,
        metodo="entities_canonical_v1_roles_v3",
        estado="confirmado",
        confianca=1.0,
    )
    return dm
