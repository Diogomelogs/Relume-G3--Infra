from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional
import re

from relluna.core.document_memory import DocumentMemory, Layer4SemanticNormalization
from relluna.core.document_memory.layer4_canonical import EntidadeCanonica
from relluna.services.evidence.signals import load_critical_signal_json
from relluna.services.entities.document_date_resolver import DocumentDateResolver

_BIRTH_DATE_MARKERS = (
    "nascimento",
    "nascto",
    "data de nascimento",
    "idade",
)

_DOCUMENT_DATE_RESOLVER = DocumentDateResolver()


def _load_signal_json(dm: DocumentMemory, key: str) -> Any:
    if key in {"page_evidence_v1", "entities_canonical_v1", "timeline_seed_v2"}:
        return load_critical_signal_json(dm, key)
    if dm.layer2 is None:
        return None
    sig = dm.layer2.sinais_documentais.get(key)
    if not sig or not getattr(sig, "valor", None):
        return None
    try:
        return json.loads(sig.valor)
    except Exception:
        return None


def _to_datetime(value: str) -> Optional[datetime]:
    if not isinstance(value, str):
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.fromisoformat(value[:10])
        except ValueError:
            return None


def _canonical_date_str(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if not isinstance(value, str):
        return None

    dt = _to_datetime(value)
    if dt is not None:
        return dt.date().isoformat()

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    return None


def _looks_like_birth_date_candidate(candidate: dict[str, Any], page_item: dict[str, Any]) -> bool:
    literal = str(candidate.get("literal") or candidate.get("date_iso") or "").lower()
    page_text = str(page_item.get("page_text") or "").lower()

    snippet = str(candidate.get("snippet") or "").lower()
    for anchor in page_item.get("anchors") or []:
        if anchor.get("label") != "date":
            continue
        if anchor.get("value") == candidate.get("date_iso") or anchor.get("snippet") == candidate.get("literal"):
            snippet = f"{snippet} {anchor.get('snippet') or ''}".strip()
            break

    if any(marker in snippet for marker in _BIRTH_DATE_MARKERS):
        return True

    idx = page_text.find(literal)
    if idx < 0:
        return False

    line_start = page_text.rfind("\n", 0, idx) + 1
    line_end = page_text.find("\n", idx)
    if line_end < 0:
        line_end = len(page_text)
    window = page_text[line_start:line_end]
    return any(marker in window for marker in _BIRTH_DATE_MARKERS)


def _is_birth_date_value(dm: DocumentMemory, value: Any) -> bool:
    candidate_iso = _canonical_date_str(value)
    if not candidate_iso:
        return False

    canonical = _load_signal_json(dm, "entities_canonical_v1") or {}
    if isinstance(canonical, dict):
        document_date = canonical.get("document_date") or {}
        quality = canonical.get("quality") or {}
        snippet = str(
            (document_date.get("evidence") or {}).get("snippet")
            or document_date.get("literal")
            or ""
        ).lower()
        warnings = {
            str(item)
            for item in (quality.get("warnings") or [])
            if isinstance(item, str)
        }
        if (
            _canonical_date_str(document_date.get("date_iso")) == candidate_iso
            and (
                "document_date_looks_like_birth_date" in warnings
                or any(marker in snippet for marker in _BIRTH_DATE_MARKERS)
            )
        ):
            return True

    page_evidence = _load_signal_json(dm, "page_evidence_v1") or []
    if not isinstance(page_evidence, list):
        return False

    for item in page_evidence:
        if not isinstance(item, dict):
            continue
        for date_candidate in item.get("date_candidates") or []:
            if not isinstance(date_candidate, dict):
                continue
            if _canonical_date_str(date_candidate.get("date_iso")) != candidate_iso:
                continue
            if _looks_like_birth_date_candidate(date_candidate, item):
                return True

    return False


def _extract_temporal_str(dm: DocumentMemory) -> Optional[str]:
    if dm.layer3 is not None:
        temporalidades = getattr(dm.layer3, "temporalidades_inferidas", None) or []
        for t in temporalidades:
            inicio = getattr(t, "inicio", None)
            valor = getattr(inicio, "valor", None) if inicio is not None else None
            if isinstance(valor, str) and valor and not _is_birth_date_value(dm, valor):
                return valor

        est = getattr(dm.layer3, "estimativa_temporal", None)
        if est is not None:
            if isinstance(est, str):
                if not _is_birth_date_value(dm, est):
                    return est
                return None
            if isinstance(est, dict):
                v = est.get("valor")
                if isinstance(v, str):
                    if not _is_birth_date_value(dm, v):
                        return v
                    return None
                if isinstance(v, datetime):
                    if not _is_birth_date_value(dm, v):
                        return v.isoformat()
                    return None
                return None

            v = getattr(est, "valor", None)
            if isinstance(v, str):
                if not _is_birth_date_value(dm, v):
                    return v
                return None
            if isinstance(v, datetime):
                if not _is_birth_date_value(dm, v):
                    return v.isoformat()
                return None

    if dm.layer2 is not None:
        exif = getattr(dm.layer2, "data_exif", None)
        if exif is not None:
            if isinstance(exif, str):
                return exif

            if isinstance(exif, dict):
                v = exif.get("valor")
                if isinstance(v, str):
                    return v
                if isinstance(v, datetime):
                    return v.isoformat()
                return None

            v = getattr(exif, "valor", None)
            if isinstance(v, str):
                return v
            if isinstance(v, datetime):
                return v.isoformat()

    canonical = _load_signal_json(dm, "entities_canonical_v1") or {}
    if isinstance(canonical, dict):
        document_date = canonical.get("document_date") or {}
        evidence = document_date.get("evidence") or {}
        snippet = str(evidence.get("snippet") or document_date.get("literal") or "").lower()
        if document_date.get("date_iso") and not any(
            marker in snippet for marker in _BIRTH_DATE_MARKERS
        ) and not _is_birth_date_value(dm, document_date.get("date_iso")):
            return str(document_date["date_iso"])

    page_evidence = _load_signal_json(dm, "page_evidence_v1") or []
    if isinstance(page_evidence, list):
        resolved = _DOCUMENT_DATE_RESOLVER.resolve(page_evidence)
        if resolved and resolved.get("date_iso"):
            return str(resolved["date_iso"])

        for item in page_evidence:
            for d in item.get("date_candidates") or []:
                if _looks_like_birth_date_candidate(d, item):
                    continue
                date_iso = d.get("date_iso")
                if date_iso:
                    return date_iso

    return None


def _extract_local_canonico(dm: DocumentMemory) -> Optional[str]:
    page_evidence = _load_signal_json(dm, "page_evidence_v1") or []
    if not isinstance(page_evidence, list):
        return None

    for item in page_evidence:
        adm = item.get("administrative_entities") or {}
        city = adm.get("city")
        uf = adm.get("uf")
        if city and uf:
            return f"{city}, {uf}"

    return None


def _looks_like_human_name(value: Optional[str]) -> bool:
    if not value:
        return False
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    if len(cleaned.split()) < 2 or len(cleaned.split()) > 6:
        return False
    low = cleaned.lower()
    if low in {"uso oral continuo", "uso oral contínuo", "urobilinogenio normal", "urobilinogênio normal", "estado de sao paulo", "estado de são paulo"}:
        return False
    if re.search(r"\b\d+(?:mg|ml|g|mcg|cm)\b", low):
        return False
    return True


def _extract_entidades(dm: DocumentMemory) -> list[EntidadeCanonica]:
    out: list[EntidadeCanonica] = []

    l3 = getattr(dm, "layer3", None)
    if l3 is not None:
        for ent in getattr(l3, "entidades_semanticas", None) or []:
            tipo = getattr(ent, "tipo", None)
            valor = getattr(ent, "valor", None)
            if tipo and valor:
                out.append(EntidadeCanonica(kind=tipo, label=valor))

    best_patient: Optional[tuple[float, str]] = None
    page_evidence = _load_signal_json(dm, "page_evidence_v1") or []
    if isinstance(page_evidence, list):
        for item in page_evidence:
            people = item.get("people") or {}
            patient_name = people.get("patient_name")
            if not _looks_like_human_name(patient_name):
                continue
            score = float(people.get("patient_confidence") or 0.0)
            taxonomy = (item.get("page_taxonomy") or {}).get("value") or ""
            if taxonomy in {"documento_medico", "laudo_medico", "receituario", "atestado_medico", "parecer_medico"}:
                score += 0.03
            if best_patient is None or score > best_patient[0]:
                best_patient = (score, patient_name)

    if best_patient:
        out.append(EntidadeCanonica(kind="paciente", label=best_patient[1]))

    dedup: list[EntidadeCanonica] = []
    seen = set()
    for e in out:
        key = (e.kind, e.label)
        if key in seen:
            continue
        seen.add(key)
        dedup.append(e)

    return dedup


def _extract_tags(dm: DocumentMemory) -> list[str]:
    tags: list[str] = []

    l3 = getattr(dm, "layer3", None)
    tipo_doc = getattr(getattr(l3, "tipo_documento", None), "valor", None) if l3 else None
    if tipo_doc:
        tags.append(tipo_doc)

    if l3 is not None:
        for ent in getattr(l3, "entidades_semanticas", None) or []:
            if getattr(ent, "tipo", None) == "cid" and getattr(ent, "valor", None):
                tags.append(f"cid:{ent.valor}")

    return list(dict.fromkeys(tags))


def normalize_to_layer4(dm: DocumentMemory) -> DocumentMemory:
    l4 = Layer4SemanticNormalization()

    valor_str = _extract_temporal_str(dm)
    if isinstance(valor_str, str):
        dt = _to_datetime(valor_str)
        if dt is not None:
            l4.data_canonica = dt
            l4.periodo = f"{dt.year:04d}-{dt.month:02d}"
        else:
            l4.data_canonica = valor_str
            if len(valor_str) >= 7:
                l4.periodo = valor_str[:7]

    l4.local_canonico = _extract_local_canonico(dm)
    l4.entidades = _extract_entidades(dm)
    l4.tags = _extract_tags(dm)
    l4.relacoes_temporais = []

    dm.layer4 = l4
    return dm


def promote_temporal_to_layer4(dm: DocumentMemory) -> DocumentMemory:
    return normalize_to_layer4(dm)
