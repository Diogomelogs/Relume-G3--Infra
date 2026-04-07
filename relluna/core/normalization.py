from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional
import re

from relluna.core.document_memory import DocumentMemory, Layer4SemanticNormalization
from relluna.core.document_memory.layer4_canonical import EntidadeCanonica


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


def _extract_temporal_str(dm: DocumentMemory) -> Optional[str]:
    if dm.layer3 is not None:
        temporalidades = getattr(dm.layer3, "temporalidades_inferidas", None) or []
        for t in temporalidades:
            inicio = getattr(t, "inicio", None)
            valor = getattr(inicio, "valor", None) if inicio is not None else None
            if isinstance(valor, str) and valor:
                return valor

        est = getattr(dm.layer3, "estimativa_temporal", None)
        if est is not None:
            if isinstance(est, str):
                return est
            if isinstance(est, dict):
                v = est.get("valor")
                if isinstance(v, str):
                    return v
                if isinstance(v, datetime):
                    return v.isoformat()
                return None

            v = getattr(est, "valor", None)
            if isinstance(v, str):
                return v
            if isinstance(v, datetime):
                return v.isoformat()

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

    page_evidence = _load_signal_json(dm, "page_evidence_v1") or []
    if isinstance(page_evidence, list):
        for item in page_evidence:
            for d in item.get("date_candidates") or []:
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