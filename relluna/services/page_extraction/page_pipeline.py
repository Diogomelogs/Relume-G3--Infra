from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.types_basic import ProvenancedString
from relluna.services.page_extraction.page_clinical_extractors import (
    extract_clinical_page_entities,
)
from relluna.services.page_extraction.page_entity_extractors import (
    extract_basic_page_entities,
)
from relluna.services.page_extraction.page_taxonomy import classify_page_subtype
from relluna.services.page_extraction.page_text_splitter import split_document_by_page

FONTE = "services.page_extraction.page_pipeline_v12"

_MONTHS_PT = {
    "janeiro": "01",
    "fevereiro": "02",
    "marco": "03",
    "março": "03",
    "abril": "04",
    "maio": "05",
    "junho": "06",
    "julho": "07",
    "agosto": "08",
    "setembro": "09",
    "outubro": "10",
    "novembro": "11",
    "dezembro": "12",
}

_RE_DATE_NUMERIC = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_RE_DATE_TEXTUAL = re.compile(
    r"\b(\d{1,2})\s+de\s+([A-Za-zçÇãÃáàâéêíóôõú]+)\s+de\s+(\d{4})\b",
    re.IGNORECASE,
)
_RE_TIMESTAMP = re.compile(
    r"\b(20\d{2})-(\d{2})-(\d{2})T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)\b"
)

# Captura com labels fortes e corte antes do próximo campo.
_RE_PATIENT_LABEL = re.compile(
    r"(?is)\b(?:nome\s+paciente|nome\s+do\s+paciente|paciente)\s*[:\-]?\s*"
    r"([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇa-záàãâéêíóôõúç'\-\s]{4,}?)"
    r"(?=\s+(?:nascimento|sexo|rghc|rg|cpf|data(?:/hora)?|idade|prontu[aá]rio|conv[eê]nio|plano|prestador|servi[cç]o|especialidade)\b|$)"
)

_RE_PATIENT_BODY = re.compile(
    r"(?i)(?:sr\.?\(a\)?|sr\(a\)|o\(a\)\s*sr\.?\(a\)?|paciente)\s*[:\-]?\s*"
    r"([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-Za-zÁÀÃÂÉÊÍÓÔÕÚÇáàãâéêíóôõúç'\-]+"
    r"(?:\s+[A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-Za-zÁÀÃÂÉÊÍÓÔÕÚÇáàãâéêíóôõúç'\-]+){1,5})"
)

_RE_MOTHER_LABEL = re.compile(
    r"(?is)\b(?:nome\s+da\s+m[ãa]e|m[ãa]e|genitora|filia[cç][aã]o)\s*[:\-]?\s*"
    r"([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇa-záàãâéêíóôõúç'\-\s]{4,}?)"
    r"(?=\s+(?:nascimento|sexo|rghc|rg|cpf|data(?:/hora)?|idade|prontu[aá]rio|conv[eê]nio|plano|prestador|servi[cç]o|especialidade)\b|$)"
)

_RE_PROVIDER_LABEL = re.compile(
    r"(?is)\b(?:prestador|m[eé]dico(?:\s+assistente)?|emitente|profissional|dr\.?|dra\.?)\s*[:\-]?\s*"
    r"([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇa-záàãâéêíóôõúç'\-\s]{4,}?)"
    r"(?=\s+(?:servi[cç]o|especialidade|crm|cid|data|assinatura|carimbo|telefone|endere[cç]o|$))"
)

_RE_PROVIDER_STRONG = re.compile(r"(?i)\b(?:dr\.?|dra\.?)\s+[A-ZÁÀÃÂÉÊÍÓÔÕÚÇ]")
_RE_PROVIDER_CRM = re.compile(r"(?i)\bcrm\b")
_RE_PATIENT_CONTEXT = re.compile(
    r"(?i)\b(est[eê]ve\s+internado|afastado|paciente|sr\.?\(a\)?|o\(a\)\s*sr)"
)
_RE_MOTHER_CONTEXT = re.compile(r"(?i)\b(m[aã]e|filia[cç][aã]o|genitora)\b")
_RE_CITY_DATE_PREFIX = re.compile(
    r"^[A-Za-zÀ-ÿ\s]+,\s*\d{1,2}\s+de\s+[A-Za-zÀ-ÿ]+\s+de\s+\d{4}",
    re.IGNORECASE,
)

_STOP_TOKENS = {
    "http",
    "https",
    "www",
    "assinado",
    "assinatura",
    "verifique",
    "valid",
    "validador",
    "timestamp",
    "hash",
    "codigo",
    "código",
    "qr",
}

_NON_NAME_TOKENS = {
    "cpf",
    "cnpj",
    "crm",
    "cid",
    "rua",
    "avenida",
    "bairro",
    "cep",
    "cidade",
    "uf",
    "telefone",
    "email",
    "site",
    "parecer",
    "atestado",
    "receituario",
    "receituário",
    "convênio",
    "convenio",
    "categoria",
    "portoseguro",
    "porto",
    "saude",
    "saúde",
    "carteirinha",
    "identificação",
    "identificacao",
    "comprador",
    "fornecedor",
    "medicamentos",
    "substâncias",
    "substancias",
    "emitente",
    "estado",
    "serviço",
    "servico",
    "especialidade",
    "nascimento",
    "sexo",
}

_PROVIDER_HINTS = {
    "dr",
    "dra",
    "crm",
    "medico",
    "médico",
    "clinica",
    "clínica",
    "hospital",
    "prestador",
    "emitente",
    "profissional",
}

_HARD_NON_PERSON_PHRASES = {
    "uso oral continuo",
    "uso oral contínuo",
    "medicamentos ou substâncias",
    "medicamentos ou substancias",
    "estado de sao paulo",
    "estado de são paulo",
    "identificação do comprador",
    "identificacao do comprador",
    "identificação do fornecedor",
    "identificacao do fornecedor",
}

_HEADER_BREAK_TOKENS = (
    "nascimento",
    "sexo",
    "rghc",
    "rg",
    "cpf",
    "idade",
    "data",
    "hora",
    "prontuário",
    "prontuario",
    "convênio",
    "convenio",
    "plano",
    "prestador",
    "serviço",
    "servico",
    "especialidade",
)


def _make_signal(dm: DocumentMemory, key: str, value: Any, metodo: str) -> DocumentMemory:
    if dm.layer2 is None:
        return dm

    dm.layer2.sinais_documentais[key] = ProvenancedString(
        valor=json.dumps(value, ensure_ascii=False),
        fonte=FONTE,
        metodo=metodo,
        estado="confirmado",
        confianca=1.0,
    )
    return dm


def _safe_lower(value: Optional[str]) -> str:
    return str(value or "").strip().lower()


def _normalize_textual_date(day: str, month_name: str, year: str) -> Optional[str]:
    mm = _MONTHS_PT.get(month_name.strip().lower())
    if not mm:
        return None
    try:
        dd = int(day)
        yyyy = int(year)
        if not (1 <= dd <= 31):
            return None
        return f"{yyyy:04d}-{int(mm):02d}-{dd:02d}"
    except Exception:
        return None


def _extract_date_candidates(page_text: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    for d, m, y in _RE_DATE_NUMERIC.findall(page_text or ""):
        out.append(
            {
                "literal": f"{d}/{m}/{y}",
                "date_iso": f"{int(y):04d}-{int(m):02d}-{int(d):02d}",
                "kind": "numeric",
            }
        )

    for d, month_name, y in _RE_DATE_TEXTUAL.findall(page_text or ""):
        iso = _normalize_textual_date(d, month_name, y)
        if iso:
            out.append(
                {
                    "literal": f"{d} de {month_name} de {y}",
                    "date_iso": iso,
                    "kind": "textual_pt",
                }
            )

    for y, m, d in _RE_TIMESTAMP.findall(page_text or ""):
        out.append(
            {
                "literal": f"{y}-{m}-{d}",
                "date_iso": f"{y}-{m}-{d}",
                "kind": "timestamp",
            }
        )

    dedup: Dict[tuple, Dict[str, Any]] = {}
    for item in out:
        dedup[(item["literal"], item["date_iso"])] = item
    return list(dedup.values())


def _trim_header_field_noise(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip(" -:|,.;")
    for token in _HEADER_BREAK_TOKENS:
        cleaned = re.sub(rf"(?i)\s+\b{re.escape(token)}\b.*$", "", cleaned).strip()
    return cleaned


def _normalize_person_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None

    text = _trim_header_field_noise(str(name))
    if len(text) < 3:
        return None

    tokens = text.split()
    clean_tokens: List[str] = []

    for token in tokens:
        low = token.lower().strip(".,;:|")
        if low in _STOP_TOKENS:
            break
        if low.startswith("http") or low.startswith("www"):
            break
        if re.fullmatch(r"[a-f0-9]{8,}", low):
            break
        clean_tokens.append(token)

    if len(clean_tokens) < 2:
        return None

    cleaned = " ".join(clean_tokens).strip()
    low_clean = cleaned.lower()

    if any(phrase in low_clean for phrase in _HARD_NON_PERSON_PHRASES):
        return None
    if any(t.lower().strip(".,;:|") in _NON_NAME_TOKENS for t in clean_tokens):
        return None
    if _RE_CITY_DATE_PREFIX.match(cleaned):
        return None
    if low_clean in {"são paulo", "sao paulo"}:
        return None
    if re.search(
        r"\b(?:medicamentos?|subst[âa]ncias?|emitente|fornecedor|comprador|identifica[cç][aã]o)\b",
        low_clean,
    ):
        return None
    if len(clean_tokens) > 8:
        return None
    if not re.fullmatch(r"[A-ZÀ-ÚA-Za-zÀ-ÿ][A-ZÀ-ÚA-Za-zÀ-ÿ\s\-']{2,}", cleaned):
        return None

    return cleaned


def _looks_like_provider(line: str) -> bool:
    low = line.lower()
    return any(hint in low for hint in _PROVIDER_HINTS)


def _token_overlap(a: Optional[str], b: Optional[str]) -> float:
    sa = {t for t in _safe_lower(a).split() if len(t) >= 2}
    sb = {t for t in _safe_lower(b).split() if len(t) >= 2}
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, min(len(sa), len(sb)))


def _find_line_index(lines: List[str], candidate: str) -> int:
    candidate_norm = _safe_lower(candidate)
    for idx, line in enumerate(lines):
        if candidate_norm and candidate_norm in _safe_lower(line):
            return idx
    return -1


def _score_patient_candidate(candidate: str, lines: List[str], full_text: str) -> float:
    if not candidate:
        return float("-inf")

    low_c = candidate.lower()
    if any(phrase in low_c for phrase in _HARD_NON_PERSON_PHRASES):
        return -20.0
    if re.search(
        r"\b(?:estado|emitente|medicamentos?|subst[âa]ncias?|fornecedor|comprador)\b",
        low_c,
    ):
        return -15.0

    score = 0.0
    idx = _find_line_index(lines, candidate)

    if idx >= 0:
        line = lines[idx]
        window = " ".join(lines[max(0, idx - 1) : min(len(lines), idx + 2)])
        wlow = _safe_lower(window)
        llow = _safe_lower(line)

        if re.search(r"(?i)\bnome\s+paciente\b|\bpaciente\s*:", line):
            score += 12.0
        if _RE_PATIENT_CONTEXT.search(window):
            score += 5.0
        if _RE_MOTHER_CONTEXT.search(window):
            score -= 6.0
        if "crm" in wlow or "dra" in wlow or "dr." in wlow or "médico" in wlow or "medico" in wlow:
            score -= 6.0
        if any(
            tok in llow
            for tok in (
                "uso oral",
                "medicamentos",
                "substâncias",
                "substancias",
                "emitente",
                "estado de",
            )
        ):
            score -= 12.0
        if idx <= 6:
            score += 1.0

    if re.search(rf"(?i)\b{re.escape(candidate)}\b", full_text):
        score += 1.0
    if re.search(rf"(?i)(?:nome\s+paciente|paciente)\s*[:\-]?\s*{re.escape(candidate)}", full_text):
        score += 10.0
    if re.search(
        rf"(?i)(esteve\s+internado\(a\)|afastado\(a\)|paciente|sr\.?\(a\)?)\D{{0,20}}{re.escape(candidate)}",
        full_text,
    ):
        score += 6.0
    if re.search(
        rf"(?i){re.escape(candidate)}\D{{0,20}}(esteve\s+internado\(a\)|afastado\(a\))",
        full_text,
    ):
        score += 6.0
    if re.search(rf"(?i){re.escape(candidate)}\s+(nascimento|sexo|rghc|cpf)\b", full_text):
        score += 2.0

    return score


def _score_mother_candidate(candidate: str, lines: List[str], full_text: str) -> float:
    if not candidate:
        return float("-inf")

    score = 0.0
    idx = _find_line_index(lines, candidate)

    if idx >= 0:
        window = " ".join(lines[max(0, idx - 1) : min(len(lines), idx + 2)])
        if _RE_MOTHER_CONTEXT.search(window):
            score += 6.0
        if _RE_PATIENT_CONTEXT.search(window):
            score -= 5.0
        if re.search(r"(?i)nome\s+da\s+m[ãa]e", window):
            score += 8.0

    if re.search(rf"(?i)(m[aã]e|filia[cç][aã]o|genitora)\D{{0,20}}{re.escape(candidate)}", full_text):
        score += 6.0

    return score


def _score_provider_candidate(candidate: str, lines: List[str], full_text: str) -> float:
    if not candidate:
        return float("-inf")

    low_c = candidate.lower()
    if any(phrase in low_c for phrase in _HARD_NON_PERSON_PHRASES):
        return -20.0
    if re.search(
        r"\b(?:medicamentos?|subst[âa]ncias?|emitente|fornecedor|comprador|identifica[cç][aã]o|estado)\b",
        low_c,
    ):
        return -15.0

    score = 0.0
    idx = _find_line_index(lines, candidate)

    if idx >= 0:
        line = lines[idx]
        window = " ".join(lines[max(0, idx - 1) : min(len(lines), idx + 2)])
        wlow = _safe_lower(window)

        if re.search(r"(?i)\b(prestador|m[eé]dico|emitente|profissional)\s*:", line):
            score += 10.0
        if "crm" in wlow:
            score += 5.0
        if _RE_MOTHER_CONTEXT.search(window):
            score -= 8.0
        if _RE_PATIENT_CONTEXT.search(window):
            score -= 6.0

    if re.search(
        rf"(?i)(prestador|m[eé]dico|emitente|profissional)\s*[:\-]?\s*{re.escape(candidate)}",
        full_text,
    ):
        score += 8.0
    if re.search(rf"(?i){re.escape(candidate)}\D{{0,20}}crm", full_text):
        score += 4.0

    return score


def _choose_best(candidates: List[str], scorer) -> Optional[str]:
    if not candidates:
        return None
    ranked = sorted(((scorer(c), c) for c in candidates), reverse=True)
    best_score, best_value = ranked[0]
    if best_score <= 0:
        return None
    return best_value


def _entity_review_state(conf: float) -> str:
    if conf >= 0.95:
        return "auto_confirmed"
    if conf >= 0.82:
        return "review_recommended"
    return "needs_review"


def _infer_patient_name(page_text: str, basic: Dict[str, Any]) -> Optional[str]:
    existing = _normalize_person_name(basic.get("patient_name"))
    text = page_text or ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    candidates: List[str] = []
    if existing:
        candidates.append(existing)

    for m in _RE_PATIENT_LABEL.finditer(text):
        candidate = _normalize_person_name(m.group(1))
        if candidate:
            candidates.append(candidate)

    for m in _RE_PATIENT_BODY.finditer(text):
        candidate = _normalize_person_name(m.group(1))
        if candidate:
            candidates.append(candidate)

    for candidate in basic.get("person_candidates", []):
        norm = _normalize_person_name(candidate)
        if not norm:
            continue
        if _looks_like_provider(norm):
            continue
        candidates.append(norm)

    deduped: List[str] = []
    seen = set()
    for c in candidates:
        key = _safe_lower(c)
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    chosen = _choose_best(deduped, lambda c: _score_patient_candidate(c, lines, text))
    if not chosen:
        return None

    chosen = _trim_header_field_noise(chosen)
    chosen = re.sub(
        r"(?i)\s+(esteve|internado\(a\)|internado|afastado\(a\)|afastado)$",
        "",
        chosen,
    ).strip()
    return chosen or None


def _infer_provider_name(page_text: str, clinical: Dict[str, Any]) -> Optional[str]:
    existing = _normalize_person_name(clinical.get("provider_name"))
    text = page_text or ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    candidates: List[str] = []

    if existing:
        candidates.append(existing)

    for m in _RE_PROVIDER_LABEL.finditer(text):
        norm = _normalize_person_name(m.group(1))
        if norm:
            candidates.append(norm)

    for line in lines:
        if _RE_PROVIDER_STRONG.search(line) or _RE_PROVIDER_CRM.search(line):
            norm = _normalize_person_name(line)
            if norm:
                candidates.append(norm)

    for idx, line in enumerate(lines):
        if "CRM" not in line.upper():
            continue

        for j in range(max(0, idx - 3), min(len(lines), idx + 3)):
            raw = lines[j].strip()
            candidate = _normalize_person_name(raw)
            if not candidate:
                continue

            low = candidate.lower()
            if low in {"são paulo", "sao paulo"}:
                continue
            if _RE_CITY_DATE_PREFIX.match(candidate):
                continue
            if "paciente" in low or "mãe" in low or "mae" in low or "cid" in low or "motivo" in low:
                continue

            candidates.append(candidate)

    deduped: List[str] = []
    seen = set()
    for c in candidates:
        key = _safe_lower(c)
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    chosen = _choose_best(deduped, lambda c: _score_provider_candidate(c, lines, text))
    return chosen


def _infer_mother_name(page_text: str, basic: Dict[str, Any], patient_name: Optional[str]) -> Optional[str]:
    existing = _normalize_person_name(basic.get("mother_name"))
    text = page_text or ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    candidates: List[str] = []

    if existing:
        candidates.append(existing)

    for m in _RE_MOTHER_LABEL.finditer(text):
        candidate = _normalize_person_name(m.group(1))
        if candidate:
            candidates.append(candidate)

    for candidate in basic.get("person_candidates", []):
        norm = _normalize_person_name(candidate)
        if not norm:
            continue
        if patient_name and _token_overlap(norm, patient_name) >= 0.8:
            continue
        candidates.append(norm)

    deduped: List[str] = []
    seen = set()
    for c in candidates:
        key = _safe_lower(c)
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    chosen = _choose_best(deduped, lambda c: _score_mother_candidate(c, lines, text))
    return chosen


def _resolve_people(
    page_text: str,
    basic: Dict[str, Any],
    clinical: Dict[str, Any],
    taxonomy: Dict[str, Any],
) -> Dict[str, Any]:
    patient = _infer_patient_name(page_text, basic)
    mother = _infer_mother_name(page_text, basic, patient)
    provider = _infer_provider_name(page_text, clinical)

    patient_conf = 0.0
    if patient:
        lines = [l.strip() for l in (page_text or "").splitlines() if l.strip()]
        raw_score = _score_patient_candidate(patient, lines, page_text or "")
        patient_conf = 0.98 if raw_score >= 12 else 0.90 if raw_score >= 8 else 0.80 if raw_score >= 4 else 0.68

    mother_conf = 0.0
    if mother:
        lines = [l.strip() for l in (page_text or "").splitlines() if l.strip()]
        raw_score = _score_mother_candidate(mother, lines, page_text or "")
        mother_conf = 0.94 if raw_score >= 10 else 0.86 if raw_score >= 6 else 0.72

    provider_conf = 0.0
    if provider:
        lines = [l.strip() for l in (page_text or "").splitlines() if l.strip()]
        raw_score = _score_provider_candidate(provider, lines, page_text or "")
        provider_conf = 0.94 if raw_score >= 10 else 0.84 if raw_score >= 6 else 0.70

    return {
        "patient_name": patient,
        "patient_confidence": patient_conf if patient else None,
        "patient_review_state": _entity_review_state(patient_conf) if patient else "needs_review",
        "mother_name": mother,
        "mother_confidence": mother_conf if mother else None,
        "mother_review_state": _entity_review_state(mother_conf) if mother else "needs_review",
        "provider_name": provider,
        "provider_confidence": provider_conf if provider else None,
        "provider_review_state": _entity_review_state(provider_conf) if provider else "needs_review",
    }


def _normalize_input_spans(page_no: int, page_text: str, raw_spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for sp in raw_spans or []:
        bbox = sp.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4 and sp.get("text"):
            out.append(
                {
                    "page": page_no,
                    "text": str(sp.get("text")).strip(),
                    "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])],
                }
            )
    return out


def _normalize_spaces(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned or None


def _find_best_span_for_value(spans: List[Dict[str, Any]], value: Optional[str]) -> Optional[Dict[str, Any]]:
    target = _normalize_spaces(value)
    if not target:
        return None

    target_low = target.lower()
    best: Optional[Dict[str, Any]] = None
    best_score = -1.0

    for sp in spans:
        sp_text = _normalize_spaces(sp.get("text"))
        if not sp_text:
            continue

        sp_low = sp_text.lower()
        score = 0.0
        if target_low == sp_low:
            score += 20.0
        if target_low in sp_low:
            score += 10.0
        overlap = _token_overlap(target_low, sp_low)
        score += overlap * 10.0

        if score > best_score:
            best_score = score
            best = sp

    return best if best_score >= 8.0 else None


def _append_anchor(
    anchors: List[Dict[str, Any]],
    page: int,
    label: str,
    value: Optional[str],
    spans: List[Dict[str, Any]],
    source_path: str,
    snippet_prefix: Optional[str] = None,
) -> None:
    if value is None or str(value).strip() == "":
        return

    span = _find_best_span_for_value(spans, str(value))
    anchors.append(
        {
            "label": label,
            "value": str(value),
            "page": page,
            "bbox": span.get("bbox") if span else None,
            "snippet": f"{snippet_prefix or label}: {value}",
            "source_path": "layer2.sinais_documentais.layout_spans_v1" if span else source_path,
        }
    )


def _build_anchors(
    page_no: int,
    page_text: str,
    spans: List[Dict[str, Any]],
    basic: Dict[str, Any],
    clinical: Dict[str, Any],
    date_candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    anchors: List[Dict[str, Any]] = []

    _append_anchor(
        anchors,
        page_no,
        "patient",
        basic.get("patient_name"),
        spans,
        "layer2.sinais_documentais.page_evidence_v1",
        "Paciente",
    )
    _append_anchor(
        anchors,
        page_no,
        "mother",
        basic.get("mother_name"),
        spans,
        "layer2.sinais_documentais.page_evidence_v1",
        "Mãe",
    )
    _append_anchor(
        anchors,
        page_no,
        "provider",
        clinical.get("provider_name"),
        spans,
        "layer2.sinais_documentais.page_evidence_v1",
        "Prestador",
    )
    _append_anchor(
        anchors,
        page_no,
        "service",
        clinical.get("service"),
        spans,
        "layer2.sinais_documentais.page_evidence_v1",
        "Serviço",
    )
    _append_anchor(
        anchors,
        page_no,
        "specialty",
        clinical.get("specialty"),
        spans,
        "layer2.sinais_documentais.page_evidence_v1",
        "Especialidade",
    )

    for crm in basic.get("crm", []) or []:
        _append_anchor(
            anchors,
            page_no,
            "crm",
            crm,
            spans,
            "layer2.sinais_documentais.page_evidence_v1",
            "CRM",
        )

    for cid in clinical.get("cids", []) or []:
        _append_anchor(
            anchors,
            page_no,
            "cid",
            cid,
            spans,
            "layer2.sinais_documentais.page_evidence_v1",
            "CID",
        )

    for dc in date_candidates:
        span = _find_best_span_for_value(spans, dc.get("literal"))
        anchors.append(
            {
                "label": "date",
                "value": dc.get("date_iso"),
                "page": page_no,
                "bbox": span.get("bbox") if span else None,
                "snippet": dc.get("literal"),
                "source_path": "layer2.sinais_documentais.layout_spans_v1" if span else "layer2.texto_ocr_literal.valor",
            }
        )

    dedup: List[Dict[str, Any]] = []
    seen = set()
    for a in anchors:
        key = (a.get("label"), a.get("value"), a.get("page"), str(a.get("bbox")))
        if key in seen:
            continue
        seen.add(key)
        dedup.append(a)
    return dedup


def _classify_signal_zone(text: str) -> str:
    low = _safe_lower(text)
    if any(
        k in low
        for k in (
            "paciente",
            "mãe",
            "mae",
            "prestador",
            "crm",
            "cid",
            "data",
            "serviço",
            "servico",
            "especialidade",
        )
    ):
        return "core_probative"
    return "institutional_context"


def _anchor_confidence(a: Dict[str, Any]) -> float:
    label = str(a.get("label") or "")
    base = 0.68
    if label in {"patient", "mother", "provider"}:
        base = 0.78
    elif label in {"crm", "cid", "date"}:
        base = 0.84
    if a.get("bbox"):
        base = min(base + 0.12, 0.99)
    return round(base, 3)


def _anchor_review_state(confidence: float) -> str:
    if confidence >= 0.95:
        return "auto_confirmed"
    if confidence >= 0.82:
        return "review_recommended"
    return "needs_review"


def _resolve_signal_zones(anchors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    signal_zones: List[Dict[str, Any]] = []

    for a in anchors:
        confidence = _anchor_confidence(a)
        signal_zones.append(
            {
                "label": a.get("label"),
                "value": a.get("value"),
                "page": a.get("page"),
                "bbox": a.get("bbox"),
                "snippet": a.get("snippet"),
                "signal_zone": _classify_signal_zone(a.get("snippet") or a.get("value") or ""),
                "confidence": confidence,
                "review_state": _anchor_review_state(confidence),
                "provenance_status": "exact" if a.get("bbox") else "missing",
                "source_path": a.get("source_path"),
            }
        )

    return signal_zones


def apply_page_analysis(dm: DocumentMemory) -> DocumentMemory:
    if dm.layer2 is None or dm.layer2.texto_ocr_literal is None:
        return dm

    split_pages = split_document_by_page(dm)
    pages: List[Dict[str, Any]] = []
    layout_spans_out: List[Dict[str, Any]] = []

    for item in split_pages:
        page_no = item["page"]
        page_text = item["text"]
        raw_spans = item.get("spans") or []
        spans = _normalize_input_spans(page_no, page_text, raw_spans)

        layout_spans_out.extend(spans)

        basic = extract_basic_page_entities(page_text)
        clinical = extract_clinical_page_entities(page_text)
        taxonomy = classify_page_subtype(page_text)

        resolved_people = _resolve_people(page_text, basic, clinical, taxonomy)

        if resolved_people.get("patient_name"):
            basic["patient_name"] = resolved_people["patient_name"]

        if resolved_people.get("mother_name"):
            basic["mother_name"] = resolved_people["mother_name"]

        if resolved_people.get("provider_name"):
            clinical["provider_name"] = resolved_people["provider_name"]

        if clinical.get("provider_name"):
            low = str(clinical["provider_name"]).strip().lower()
            if low in {
                "são paulo",
                "sao paulo",
                "medicamentos ou substâncias",
                "medicamentos ou substancias",
            }:
                clinical["provider_name"] = None

        basic["cpf"] = [
            v
            for v in basic.get("cpf", [])
            if re.sub(r"\D", "", str(v)) and len(re.sub(r"\D", "", str(v))) == 11
        ]
        basic["phones"] = [
            v for v in basic.get("phones", []) if str(v) != "(63) 2831-2326"
        ]

        if basic.get("patient_name") and _normalize_person_name(basic["patient_name"]) is None:
            basic["patient_name"] = None
            resolved_people["patient_confidence"] = None
            resolved_people["patient_review_state"] = "needs_review"

        if basic.get("mother_name") and _normalize_person_name(basic["mother_name"]) is None:
            basic["mother_name"] = None
            resolved_people["mother_confidence"] = None
            resolved_people["mother_review_state"] = "needs_review"

        if clinical.get("provider_name") and _normalize_person_name(clinical["provider_name"]) is None:
            clinical["provider_name"] = None
            resolved_people["provider_confidence"] = None
            resolved_people["provider_review_state"] = "needs_review"

        date_candidates = _extract_date_candidates(page_text)
        anchors = _build_anchors(page_no, page_text, spans, basic, clinical, date_candidates)

        for a in anchors:
            has_exact_bbox = bool(a.get("bbox"))
            a["provenance_status"] = "exact" if has_exact_bbox else "missing"
            a["confidence"] = 0.97 if has_exact_bbox else _anchor_confidence(a)
            a["review_state"] = "auto_confirmed" if has_exact_bbox else _anchor_review_state(a["confidence"])
            a["signal_zone"] = _classify_signal_zone(a.get("snippet") or a.get("value") or "")
            a.setdefault(
                "source_path",
                "layer2.sinais_documentais.layout_spans_v1"
                if has_exact_bbox
                else "layer2.sinais_documentais.page_evidence_v1",
            )

        signal_zones = _resolve_signal_zones(anchors)

        pages.append(
            {
                "page": page_no,
                "subdoc_id": item.get("subdoc_id"),
                "page_text": page_text,
                "page_taxonomy": taxonomy,
                "people": {
                    "patient_name": basic.get("patient_name"),
                    "patient_confidence": resolved_people.get("patient_confidence"),
                    "patient_review_state": resolved_people.get("patient_review_state"),
                    "mother_name": basic.get("mother_name"),
                    "mother_confidence": resolved_people.get("mother_confidence"),
                    "mother_review_state": resolved_people.get("mother_review_state"),
                    "provider_name": clinical.get("provider_name"),
                    "provider_confidence": resolved_people.get("provider_confidence"),
                    "provider_review_state": resolved_people.get("provider_review_state"),
                },
                "administrative_entities": {
                    "rghc": basic.get("rghc"),
                    "cpf": basic.get("cpf", []),
                    "cnpj": basic.get("cnpj", []),
                    "crm": basic.get("crm", []),
                    "phones": basic.get("phones", []),
                    "organizations": basic.get("organizations", []),
                    "address_line": basic.get("address_line"),
                    "cep": basic.get("cep"),
                    "city": basic.get("city"),
                    "uf": basic.get("uf"),
                },
                "date_candidates": date_candidates,
                "clinical_entities": clinical,
                "signal_zones": signal_zones,
                "anchors": anchors,
            }
        )

    dm = _make_signal(
        dm,
        "layout_spans_v1",
        layout_spans_out,
        metodo="ocr_real_spans_or_page_split_spans_v3",
    )

    dm = _make_signal(
        dm,
        "page_evidence_v1",
        pages,
        metodo="page_split_real+entities_v7+clinical_v6+taxonomy_v2+anchors_v7+bbox_real_integration_v3",
    )

    return dm