from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Dict, List, Optional

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.types_basic import ProvenancedString

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


def _load_signal_json(dm: DocumentMemory, key: str) -> Any:
    if dm.layer2 is None:
        return None
    sig = dm.layer2.sinais_documentais.get(key)
    if not sig or not getattr(sig, "valor", None):
        return None
    try:
        return json.loads(sig.valor)
    except Exception:
        return None


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
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    basis = f"{date_iso}|{event_hint}|{page}|{snippet or date_literal or ''}|{source_path}"
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
            item.get("page"),
            item.get("snippet"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)

    out.sort(key=lambda x: (x["date_iso"], x.get("priority", 500), x["seed_id"]))
    return out


def _build_from_entities_canonical(
    dm: DocumentMemory,
    canonical: Dict[str, Any],
) -> List[Dict[str, Any]]:
    seeds: List[Dict[str, Any]] = []

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
                        extra=extra,
                    )
                )

        # se já conseguiu eventos clínicos, não cair para emissão genérica
        if seeds:
            return _dedup(seeds)

    # parecer/documento: fallback documental
    if document_date.get("date_iso"):
        ev = document_date.get("evidence") or {}
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
                extra={
                    "document_type": document_type,
                    "provider_name": provider.get("name"),
                },
            )
        )

    # parecer médico: condição clínica
    if document_type == "parecer_medico" and clinical.get("cids") and document_date.get("date_iso"):
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
                extra={
                    "document_type": document_type,
                    "cids": cid_codes,
                    "provider_name": provider.get("name"),
                },
            )
        )

    return _dedup(seeds)


def build_timeline_seeds_v2(dm: DocumentMemory) -> List[Dict[str, Any]]:
    canonical = _load_signal_json(dm, "entities_canonical_v1")

    if isinstance(canonical, dict):
        return _build_from_entities_canonical(dm, canonical)

    return []


def seed_timeline_v2(dm: DocumentMemory) -> DocumentMemory:
    if dm.layer2 is None:
        return dm

    seeds = build_timeline_seeds_v2(dm)
    if not seeds:
        return dm

    dm.layer2.sinais_documentais["timeline_seed_v2"] = ProvenancedString(
        valor=json.dumps(seeds, ensure_ascii=False),
        fonte=FONTE,
        metodo="entities_canonical_v1_roles_v3",
        estado="confirmado",
        confianca=1.0,
    )
    return dm