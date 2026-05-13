from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.types_basic import ProvenancedString
from relluna.services.evidence.signals import dump_critical_signal_json, load_critical_signal_json
from relluna.services.entities.document_date_resolver import DocumentDateResolver
from relluna.services.entities.people_resolver import PeopleResolver
from relluna.services.legal.legal_canonical_fields_v1 import apply_legal_canonical_fields_v1

FONTE = "services.entities.entities_canonical_v1"

_SIGNAL_ZONE_PRIORITY = {
    "core_probative": 0,
    "institutional_context": 1,
}

_RE_DATE_DDMMYYYY = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
_RE_TEXTUAL_DOC_DATE = re.compile(
    r"\b(?:SAO PAULO|SÃO PAULO)\s*,?\s*(\d{1,2}\s+de\s+[A-Za-zçÇãõáéíóúÁÉÍÓÚ]+\s+de\s+\d{4})",
    re.IGNORECASE,
)
_RE_PATIENT_INLINE = re.compile(
    r"\bNome\s+([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-Za-zÁÀÃÂÉÊÍÓÔÕÚÇáàãâéêíóôõúç\s]+?)\s+Prontuário\b",
    re.IGNORECASE,
)
_RE_PATIENT_HEADER = re.compile(
    r"\b(?:Paciente|Nome(?:\s+Paciente)?)(?!\s+da\s+m[ãa]e)\s*:\s*"
    r"([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-Za-zÁÀÃÂÉÊÍÓÔÕÚÇáàãâéêíóôõúç\s]+?)"
    r"(?=\s+(?:Nome\s+da\s+m[ãa]e|M[ãa]e|Genitora|Filia[cç][aã]o|Nascimento|Sexo|RGHC|RG|CPF|Data(?:/Hora)?|Idade|Prontu[aá]rio|Conv[eê]nio|Plano|Prestador|Servi[cç]o|Especialidade)\b|$)",
    re.IGNORECASE,
)
_RE_ATTESTADO = re.compile(r"\bATESTADO\b", re.IGNORECASE)
_RE_CID = re.compile(r"\bCID\b", re.IGNORECASE)
_RE_CRM = re.compile(r"\bCRM\b", re.IGNORECASE)
_RE_INTERNADO = re.compile(r"internado\(a\)", re.IGNORECASE)

_HARD_NON_PERSON = {
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
    "urobilinogenio normal",
    "urobilinogênio normal",
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

_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

_BIRTH_DATE_MARKERS = (
    "nascimento",
    "nascto",
    "data de nascimento",
    "idade",
)

_DOCUMENT_DATE_RESOLVER = DocumentDateResolver()
_PEOPLE_RESOLVER = PeopleResolver()


def _load_signal_json(dm: DocumentMemory, key: str) -> Any:
    return load_critical_signal_json(dm, key)


def _make_signal(dm: DocumentMemory, key: str, value: Any, metodo: str) -> DocumentMemory:
    if dm.layer2 is None:
        return dm

    dm.layer2.sinais_documentais[key] = ProvenancedString(
        valor=dump_critical_signal_json(key, value, dm=dm),
        fonte=FONTE,
        metodo=metodo,
        estado="confirmado",
        confianca=1.0,
    )
    return dm


def _safe_text(dm: DocumentMemory) -> str:
    if dm.layer2 and dm.layer2.texto_ocr_literal and dm.layer2.texto_ocr_literal.valor:
        return dm.layer2.texto_ocr_literal.valor
    return ""


def _all_page_evidence(dm: DocumentMemory) -> List[Dict[str, Any]]:
    page_evidence = _load_signal_json(dm, "page_evidence_v1") or []
    if isinstance(page_evidence, list):
        return [x for x in page_evidence if isinstance(x, dict)]
    return []


def _group_page_items_by_subdoc(page_items: List[Dict[str, Any]]) -> List[Tuple[str, List[Dict[str, Any]]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for item in page_items:
        if not isinstance(item, dict):
            continue
        subdoc_id = str(item.get("subdoc_id") or "__document__")
        grouped.setdefault(subdoc_id, []).append(item)

    def _sort_key(entry: Tuple[str, List[Dict[str, Any]]]) -> Tuple[int, str]:
        subdoc_id, items = entry
        first_page = min(
            int(item.get("page") or 999999)
            for item in items
            if isinstance(item, dict)
        )
        return first_page, subdoc_id

    return sorted(grouped.items(), key=_sort_key)


def _normalize_spaces(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned or None


def _trim_header_field_noise(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None

    cleaned = _normalize_spaces(text)
    if not cleaned:
        return None

    for token in _HEADER_BREAK_TOKENS:
        cleaned = re.sub(rf"(?i)\s+\b{re.escape(token)}\b.*$", "", cleaned).strip()

    cleaned = cleaned.strip(" -:|,.;")
    return cleaned or None


def _parse_br_date(date_literal: str) -> Optional[str]:
    m = _RE_DATE_DDMMYYYY.search(date_literal or "")
    if not m:
        return None
    dd, mm, yyyy = m.group(1).split("/")
    return f"{yyyy}-{mm}-{dd}"


def _parse_pt_textual_date(date_literal: str) -> Optional[str]:
    m = re.search(
        r"(\d{1,2})\s+de\s+([A-Za-zçÇãõáéíóúÁÉÍÓÚ]+)\s+de\s+(\d{4})",
        date_literal or "",
        re.IGNORECASE,
    )
    if not m:
        return None

    day = int(m.group(1))
    month_name = m.group(2).lower()
    year = int(m.group(3))
    month = _MONTHS.get(month_name)
    if not month:
        return None

    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except Exception:
        return None


def _find_patient_from_text(text: str) -> Optional[str]:
    m_inline = _RE_PATIENT_INLINE.search(text or "")
    if m_inline:
        candidate = _trim_header_field_noise(m_inline.group(1))
        if _looks_like_patient_name(candidate):
            return candidate

    m_header = _RE_PATIENT_HEADER.search(text or "")
    if m_header:
        candidate = _trim_header_field_noise(m_header.group(1))
        if _looks_like_patient_name(candidate, m_header.group(0)):
            return candidate

    return None


def _has_strong_patient_context(snippet: Optional[str]) -> bool:
    text = _trim_header_field_noise(snippet)
    if not text:
        return False
    low = text.lower()
    if "nome da mãe" in low or "nome da mae" in low:
        return False
    return bool(re.search(r"\b(?:paciente|nome\s+paciente|nome)\s*:", text, re.IGNORECASE))


def _find_span_by_snippet(layout_spans: List[Dict[str, Any]], needle: str) -> Optional[Dict[str, Any]]:
    if not needle:
        return None
    needle_norm = _normalize_spaces(needle) or ""
    for span in layout_spans or []:
        text = _normalize_spaces(span.get("text"))
        if text and needle_norm in text:
            return span
    return None


def _score_zone_priority(zone_name: Optional[str]) -> int:
    return _SIGNAL_ZONE_PRIORITY.get(str(zone_name or ""), 99)


def _page_rank(page_item: Dict[str, Any]) -> int:
    taxonomy = ((page_item.get("page_taxonomy") or {}).get("value") or "").lower()
    if taxonomy in {"atestado_medico", "parecer_medico", "laudo_medico"}:
        return 0
    if taxonomy in {"documento_composto"}:
        return 1
    if taxonomy in {"documento_medico"}:
        return 2
    if taxonomy in {"formulario_administrativo"}:
        return 4
    return 3


def _best_anchor_for_label(page_item: Dict[str, Any], label: str) -> Optional[Dict[str, Any]]:
    anchors = page_item.get("anchors") or []
    candidates = [a for a in anchors if a.get("label") == label]
    if not candidates:
        return None

    def _sort_key(a: Dict[str, Any]) -> Tuple[int, int, float]:
        return (
            _score_zone_priority(a.get("signal_zone")),
            0 if a.get("bbox") else 1,
            -(float(a.get("confidence") or 0.0)),
        )

    candidates.sort(key=_sort_key)
    return candidates[0]


def _contains_implausible_text(value: str) -> bool:
    low = value.lower()

    if any(x in low for x in _HARD_NON_PERSON):
        return True

    if re.search(
        r"\b(?:medicamentos?|subst[âa]ncias?|emitente|fornecedor|comprador|identifica[cç][aã]o|estado|normal|servi[cç]o|especialidade)\b",
        low,
    ):
        return True

    return False


def _looks_like_person(value: Optional[str]) -> bool:
    value = _trim_header_field_noise(value)
    if not value:
        return False

    if _contains_implausible_text(value):
        return False

    if len(value.split()) < 2:
        return False
    if len(value.split()) > 8:
        return False
    if re.search(r"\d", value):
        return False
    if value.lower() in {"são paulo", "sao paulo"}:
        return False

    return True


def _looks_like_patient_name(value: Optional[str], snippet: Optional[str] = None) -> bool:
    value = _trim_header_field_noise(value)
    if not value:
        return False

    if not _looks_like_person(value):
        return False

    tokens = value.split()
    if len(tokens) < 3 and not _has_strong_patient_context(snippet):
        return False

    strong_tokens = [t for t in tokens if len(t) >= 4]
    if len(strong_tokens) < 2:
        return False

    if all(len(t) <= 3 for t in tokens):
        return False

    if re.fullmatch(r"[A-Z]{1,3}\s+[A-Z]{1,3}", value):
        return False

    return True


def _looks_like_mother_name(value: Optional[str]) -> bool:
    return _looks_like_patient_name(value)


def _looks_like_provider_name(value: Optional[str]) -> bool:
    value = _trim_header_field_noise(value)
    if not value:
        return False
    if not _looks_like_person(value):
        return False

    tokens = value.split()
    if len(tokens) < 2:
        return False

    strong_tokens = [t for t in tokens if len(t) >= 3]
    if len(strong_tokens) < 2:
        return False

    return True


def _candidate_from_people(page_item: Dict[str, Any], role_key: str, fallback_prefix: str) -> Optional[Dict[str, Any]]:
    people = page_item.get("people") or {}
    name = _trim_header_field_noise(people.get(role_key))
    label_map = {
        "patient_name": "patient",
        "mother_name": "mother",
        "provider_name": "provider",
    }
    anchor = _best_anchor_for_label(page_item, label_map[role_key])

    if role_key == "patient_name" and not _looks_like_patient_name(name, anchor.get("snippet") if anchor else None):
        return None
    if role_key == "mother_name" and not _looks_like_mother_name(name):
        return None
    if role_key == "provider_name" and not _looks_like_provider_name(name):
        return None

    confidence_key = role_key.replace("_name", "_confidence")
    review_key = role_key.replace("_name", "_review_state")
    conf = float(people.get(confidence_key) or 0.0)
    review = people.get(review_key) or "review_recommended"

    return {
        "name": name,
        "confidence": conf or 0.70,
        "review_state": review,
        "page": page_item.get("page"),
        "bbox": anchor.get("bbox") if anchor else None,
        "snippet": anchor.get("snippet") if anchor else f"{fallback_prefix}: {name}",
        "source_path": anchor.get("source_path") if anchor else "layer2.sinais_documentais.page_evidence_v1",
        "provenance_status": "exact" if anchor and anchor.get("bbox") else "text_fallback",
        "page_rank": _page_rank(page_item),
        "taxonomy": ((page_item.get("page_taxonomy") or {}).get("value") or "").lower(),
    }


def _score_patient_candidate(cand: Dict[str, Any]) -> float:
    score = float(cand["confidence"])

    name = str(cand["name"])
    tokens = name.split()

    if cand.get("bbox"):
        score += 0.04

    score -= cand.get("page_rank", 0) * 0.04

    if len(tokens) >= 3:
        score += 0.06
    if len(tokens) >= 4:
        score += 0.03

    if len(tokens) <= 2:
        score -= 0.50

    short_tokens = [t for t in tokens if len(t) <= 2]
    if len(short_tokens) >= 2:
        score -= 0.45

    if cand.get("taxonomy") == "documento_composto":
        score += 0.08

    snippet = str(cand.get("snippet") or "").lower()
    if "paciente:" in snippet or "nome paciente" in snippet:
        score += 0.08

    return score


def _score_mother_candidate(cand: Dict[str, Any]) -> float:
    score = float(cand["confidence"])
    if cand.get("bbox"):
        score += 0.04
    score -= cand.get("page_rank", 0) * 0.03
    if cand.get("taxonomy") == "documento_composto":
        score += 0.05
    return score


def _score_provider_candidate(cand: Dict[str, Any]) -> float:
    score = float(cand["confidence"])
    if cand.get("bbox"):
        score += 0.04
    score -= cand.get("page_rank", 0) * 0.03
    if cand.get("crm"):
        score += 0.08
    if cand.get("taxonomy") == "documento_composto":
        score += 0.05
    return score


def _pick_best_patient(
    page_items: List[Dict[str, Any]],
    text: str,
    layout_spans: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for page_item in page_items:
        cand = _candidate_from_people(page_item, "patient_name", "Paciente")
        if cand:
            cand["_score"] = _score_patient_candidate(cand)
            candidates.append(cand)

    if not candidates:
        patient_name = _find_patient_from_text(text)
        if patient_name:
            span = _find_span_by_snippet(layout_spans, patient_name)
            return {
                "name": patient_name,
                "confidence": 0.84 if span else 0.74,
                "review_state": "review_recommended" if span else "needs_review",
                "evidence": {
                    "page": span.get("page") if span else 1,
                    "bbox": span.get("bbox") if span else None,
                    "snippet": f"Paciente: {patient_name}",
                    "source_path": "layer2.sinais_documentais.layout_spans_v1"
                    if span
                    else "layer2.texto_ocr_literal.valor",
                    "provenance_status": "exact" if span else "text_fallback",
                },
            }
        return None

    candidates.sort(
        key=lambda c: (
            -float(c["_score"]),
            0 if c.get("bbox") else 1,
            c.get("page_rank", 99),
            c.get("page", 999),
        )
    )
    best = candidates[0]

    return {
        "name": best["name"],
        "confidence": round(float(best["confidence"]), 3),
        "review_state": best["review_state"],
        "evidence": {
            "page": best.get("page", 1),
            "bbox": best.get("bbox"),
            "snippet": best.get("snippet") or f"Paciente: {best['name']}",
            "source_path": best.get("source_path") or "layer2.sinais_documentais.page_evidence_v1",
            "provenance_status": best.get("provenance_status") or "text_fallback",
        },
    }


def _extract_provider_name(raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    raw = _trim_header_field_noise(raw)
    if not raw or not _looks_like_provider_name(raw):
        return None, None

    tokens = raw.split()
    if len(tokens) >= 3:
        for idx in range(len(tokens) - 1, 0, -1):
            tail = " ".join(tokens[idx:])
            if any(word.lower() in tail.lower() for word in ["médico", "medico", "clínico", "clinico"]):
                head = " ".join(tokens[:idx]).strip()
                if _looks_like_provider_name(head):
                    return head, tail
    return raw, None


def _normalize_crm(raw_values: List[str], text: str) -> Optional[Dict[str, Any]]:
    candidates = list(raw_values or [])

    m = re.search(r"\bCRM\s*[-:]?\s*([0-9]{4,8})\s*([A-Z]{2})?\b", text or "", re.IGNORECASE)
    if m:
        number = m.group(1)
        uf = m.group(2)
        candidates.append(f"CRM {number}" + (f" {uf}" if uf else ""))

    for raw in candidates:
        m2 = re.search(r"\bCRM\s*[-:]?\s*([0-9]{4,8})\s*([A-Z]{2})?\b", raw or "", re.IGNORECASE)
        if m2:
            number = m2.group(1)
            uf = m2.group(2)
            return {
                "number": number,
                "uf": uf,
                "display": f"CRM {number}" + (f" {uf}" if uf else ""),
            }

    return None


def _pick_best_provider(page_items: List[Dict[str, Any]], text: str) -> Optional[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for page_item in page_items:
        people = page_item.get("people") or {}
        name_raw = people.get("provider_name")
        name, role = _extract_provider_name(name_raw)
        if not name:
            continue

        anchor = _best_anchor_for_label(page_item, "provider")
        crm = _normalize_crm(
            (page_item.get("administrative_entities") or {}).get("crm") or [],
            page_item.get("page_text") or "",
        )

        conf = float(people.get("provider_confidence") or 0.0)
        review = people.get("provider_review_state") or "review_recommended"

        cand = {
            "name": name,
            "role": role,
            "crm": crm,
            "confidence": conf or 0.70,
            "review_state": review,
            "page": page_item.get("page"),
            "bbox": anchor.get("bbox") if anchor else None,
            "snippet": anchor.get("snippet") if anchor else f"{name}" + (f" / {crm['display']}" if crm else ""),
            "source_path": anchor.get("source_path") if anchor else "layer2.sinais_documentais.page_evidence_v1",
            "provenance_status": "exact" if anchor and anchor.get("bbox") else "snippet_only",
            "page_rank": _page_rank(page_item),
            "taxonomy": ((page_item.get("page_taxonomy") or {}).get("value") or "").lower(),
        }
        cand["_score"] = _score_provider_candidate(cand)
        candidates.append(cand)

    if not candidates:
        return None

    candidates.sort(
        key=lambda c: (
            -float(c["_score"]),
            0 if c.get("bbox") else 1,
            c.get("page", 999),
        )
    )
    best = candidates[0]

    return {
        "name": best["name"],
        "role": best["role"],
        "confidence": round(float(best["confidence"]), 3),
        "review_state": best["review_state"],
        "crm": best["crm"],
        "evidence": {
            "page": best.get("page", 1),
            "bbox": best.get("bbox"),
            "snippet": best.get("snippet") or best["name"],
            "source_path": best.get("source_path"),
            "provenance_status": best.get("provenance_status"),
        },
    }


def _pick_best_mother(page_items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for page_item in page_items:
        cand = _candidate_from_people(page_item, "mother_name", "Mãe")
        if not cand:
            continue

        cand["_score"] = _score_mother_candidate(cand)
        candidates.append(cand)

    if not candidates:
        return None

    candidates.sort(
        key=lambda c: (
            -float(c["_score"]),
            0 if c.get("bbox") else 1,
            c.get("page", 999),
        )
    )
    best = candidates[0]

    return {
        "name": best["name"],
        "confidence": round(float(best["confidence"]), 3),
        "review_state": best["review_state"],
        "evidence": {
            "page": best.get("page", 1),
            "bbox": best.get("bbox"),
            "snippet": best.get("snippet") or f"Mãe: {best['name']}",
            "source_path": best.get("source_path"),
            "provenance_status": best.get("provenance_status"),
        },
    }


def _date_context_penalty(snippet: str, page_text: str, literal: str) -> float:
    snippet_low = str(snippet or "").lower()
    text_low = str(page_text or "").lower()
    literal_low = str(literal or "").lower()

    penalty = 0.0

    issue_markers = [
        "data:",
        "emissão",
        "emissao",
        "são paulo,",
        "sao paulo,",
        "assinatura",
        "receituario",
        "receituário",
    ]

    if any(m in snippet_low for m in _BIRTH_DATE_MARKERS):
        penalty -= 1.0

    idx = text_low.find(literal_low)
    if idx >= 0:
        line_start = text_low.rfind("\n", 0, idx) + 1
        line_end = text_low.find("\n", idx)
        if line_end < 0:
            line_end = len(text_low)
        window = text_low[line_start:line_end]

        if any(m in window for m in _BIRTH_DATE_MARKERS):
            penalty -= 1.2
        if any(m in window for m in issue_markers):
            penalty += 0.45

    return penalty


def _looks_like_birth_date_context(snippet: str, page_text: str, literal: str) -> bool:
    snippet_low = str(snippet or "").lower()
    text_low = str(page_text or "").lower()
    literal_low = str(literal or "").lower()

    if any(marker in snippet_low for marker in _BIRTH_DATE_MARKERS):
        return True

    idx = text_low.find(literal_low)
    if idx < 0:
        return False

    line_start = text_low.rfind("\n", 0, idx) + 1
    line_end = text_low.find("\n", idx)
    if line_end < 0:
        line_end = len(text_low)
    window = text_low[line_start:line_end]
    return any(marker in window for marker in _BIRTH_DATE_MARKERS)


def _pick_document_date(page_items: List[Dict[str, Any]], text: str) -> Optional[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for page_item in page_items:
        page_text = page_item.get("page_text") or ""

        for item in page_item.get("date_candidates") or []:
            literal = item.get("literal")
            date_iso = item.get("date_iso")
            if not literal or not date_iso:
                continue

            anchor = None
            for a in page_item.get("anchors") or []:
                if a.get("label") == "date" and (a.get("value") == date_iso or a.get("snippet") == literal):
                    anchor = a
                    break

            snippet = anchor.get("snippet") if anchor else literal
            if _looks_like_birth_date_context(snippet, page_text, literal):
                continue

            score = 0.70
            if anchor and anchor.get("bbox"):
                score += 0.20
            if _page_rank(page_item) <= 1:
                score += 0.05

            score += _date_context_penalty(snippet, page_text, literal)

            candidates.append(
                {
                    "date_iso": date_iso,
                    "literal": literal,
                    "confidence": 0.97 if anchor and anchor.get("bbox") else round(max(score, 0.05), 3),
                    "review_state": "auto_confirmed" if anchor and anchor.get("bbox") else "review_recommended",
                    "page": page_item.get("page"),
                    "bbox": anchor.get("bbox") if anchor else None,
                    "snippet": snippet,
                    "source_path": anchor.get("source_path") if anchor else "layer2.texto_ocr_literal.valor",
                    "provenance_status": "exact" if anchor and anchor.get("bbox") else "text_fallback",
                    "_score": score,
                }
            )

    if not candidates:
        m = _RE_TEXTUAL_DOC_DATE.search(text or "")
        if m:
            literal = m.group(1)
            date_iso = _parse_pt_textual_date(literal)
            if date_iso:
                return {
                    "date_iso": date_iso,
                    "literal": literal,
                    "confidence": 0.78,
                    "review_state": "review_recommended",
                    "evidence": {
                        "page": 1,
                        "bbox": None,
                        "snippet": literal,
                        "source_path": "layer2.texto_ocr_literal.valor",
                        "provenance_status": "text_fallback",
                    },
                }

    if not candidates:
        return None

    candidates = [c for c in candidates if c["_score"] > 0.20]
    if not candidates:
        return None

    candidates.sort(
        key=lambda c: (
            -(1.0 if c.get("bbox") else 0.0),
            -float(c["_score"]),
            c.get("page", 999),
        )
    )
    best = candidates[0]

    return {
        "date_iso": best["date_iso"],
        "literal": best["literal"],
        "confidence": best["confidence"],
        "review_state": best["review_state"],
        "evidence": {
            "page": best["page"],
            "bbox": best.get("bbox"),
            "snippet": best["snippet"],
            "source_path": best["source_path"],
            "provenance_status": best["provenance_status"],
        },
    }


def _pick_clinical(page_items: List[Dict[str, Any]], text: str) -> Dict[str, Any]:
    cids: List[Dict[str, Any]] = []
    service_text: Optional[str] = None
    reason_text: Optional[str] = None

    for page_item in page_items:
        clinical = page_item.get("clinical_entities") or {}
        anchors = page_item.get("anchors") or []

        if not service_text and clinical.get("service"):
            service_text = clinical.get("service")
        if not reason_text and clinical.get("reason_text"):
            reason_text = clinical.get("reason_text")

        for code in clinical.get("cids") or []:
            if not code or not re.fullmatch(r"[A-Z]\d{2}(?:\.\d)?", str(code)):
                continue

            anchor = None
            for a in anchors:
                if a.get("label") == "cid" and a.get("value") == code:
                    anchor = a
                    break

            cids.append(
                {
                    "code": str(code),
                    "evidence": {
                        "page": page_item.get("page"),
                        "bbox": anchor.get("bbox") if anchor else None,
                        "snippet": anchor.get("snippet") if anchor else f"CID: {code}",
                        "source_path": anchor.get("source_path")
                        if anchor
                        else "layer2.sinais_documentais.page_evidence_v1",
                        "provenance_status": "exact" if anchor and anchor.get("bbox") else "snippet_only",
                    },
                    "assertion_level": "observed" if anchor and anchor.get("bbox") else "inferred",
                    "_score": (
                        (0.9 if anchor and anchor.get("bbox") else 0.7)
                        - (_page_rank(page_item) * 0.03)
                    ),
                }
            )

    dedup: Dict[str, Dict[str, Any]] = {}
    for item in cids:
        code = item["code"]
        if code not in dedup or item["_score"] > dedup[code]["_score"]:
            dedup[code] = item

    cids_out = []
    for item in dedup.values():
        item.pop("_score", None)
        cids_out.append(item)

    cids_out.sort(key=lambda x: (x["evidence"].get("page") or 999, x["code"]))

    return {
        "cids": cids_out,
        "reason_text": reason_text,
        "service_text": service_text,
    }


def _first_evidence_ref(resolution: Dict[str, Any]) -> Dict[str, Any]:
    evidence_refs = resolution.get("evidence_refs") or []
    if evidence_refs and isinstance(evidence_refs[0], dict):
        return evidence_refs[0]
    return {}


def _assertion_level_from_evidence(evidence: Optional[Dict[str, Any]]) -> str:
    if not isinstance(evidence, dict):
        return "unknown"
    provenance = str(evidence.get("provenance_status") or "").lower()
    if evidence.get("bbox") and provenance == "exact":
        return "observed"
    if provenance in {"inferred", "estimated", "text_fallback", "snippet_only"}:
        return "inferred"
    return "unknown"


def _person_resolution_to_legacy(resolution: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not resolution:
        return None
    evidence = _first_evidence_ref(resolution)
    payload = {
        "name": resolution["name"],
        "confidence": resolution["confidence"],
        "review_state": resolution.get("review_state") or "review_recommended",
        "evidence": evidence,
        "evidence_refs": resolution.get("evidence_refs") or [],
        "assertion_level": _assertion_level_from_evidence(evidence),
        "resolution": {
            "reason": resolution.get("reason"),
            "confidence": resolution.get("confidence"),
        },
    }
    if "role" in resolution:
        payload["role"] = resolution.get("role")
    if "crm" in resolution:
        payload["crm"] = resolution.get("crm")
    return payload


def _document_date_resolution_to_legacy(resolution: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not resolution:
        return None
    evidence = _first_evidence_ref(resolution)
    return {
        "date_iso": resolution["date_iso"],
        "literal": resolution["literal"],
        "confidence": resolution["confidence"],
        "review_state": resolution.get("review_state") or "review_recommended",
        "evidence": evidence,
        "evidence_refs": resolution.get("evidence_refs") or [],
        "assertion_level": _assertion_level_from_evidence(evidence),
        "resolution": {
            "reason": resolution.get("reason"),
            "confidence": resolution.get("confidence"),
        },
    }


def _parse_internacao_afastamento(text: str, page_item: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    page = page_item.get("page", 1)

    m_int = re.search(
        r"internado\(a\).*?do\s+dia\s+(\d{2}/\d{2}/\d{4})\s+ao\s+dia\s+(\d{2}/\d{2}/\d{4})",
        text or "",
        re.IGNORECASE | re.DOTALL,
    )

    if m_int:
        d1, d2 = m_int.group(1), m_int.group(2)
        d1_iso, d2_iso = _parse_br_date(d1), _parse_br_date(d2)
        snippet = f"internado(a) do dia {d1} ao dia {d2}"

        result["internacao"] = {
            "start": {
                "date_iso": d1_iso,
                "literal": d1,
                "confidence": 0.96,
                "evidence": {
                    "page": page,
                    "bbox": None,
                    "snippet": snippet,
                    "source_path": "layer2.texto_ocr_literal.valor",
                    "provenance_status": "text_fallback",
                },
            },
            "end": {
                "date_iso": d2_iso,
                "literal": d2,
                "confidence": 0.96,
                "evidence": {
                    "page": page,
                    "bbox": None,
                    "snippet": snippet,
                    "source_path": "layer2.texto_ocr_literal.valor",
                    "provenance_status": "text_fallback",
                },
            },
        }

    m_af = re.search(r"afastado\(a\)\s+por\s+(\d+)\s+dia\(s\)", text or "", re.IGNORECASE)
    if m_af:
        dur = int(m_af.group(1))
        start_iso = result.get("internacao", {}).get("end", {}).get("date_iso")
        start_literal = result.get("internacao", {}).get("end", {}).get("literal")

        afastamento: Dict[str, Any] = {
            "duration_days": {
                "value": dur,
                "confidence": 0.90,
            }
        }

        if start_iso:
            base_dt = datetime.strptime(start_iso, "%Y-%m-%d")
            end_dt = base_dt + timedelta(days=dur)

            afastamento["start"] = {
                "date_iso": start_iso,
                "literal": start_literal,
                "confidence": 0.90,
                "evidence": {
                    "page": page,
                    "bbox": None,
                    "snippet": f"afastado(a) por {dur} dia(s), a partir desta data",
                    "source_path": "layer2.texto_ocr_literal.valor",
                    "provenance_status": "text_fallback",
                },
            }

            afastamento["estimated_end"] = {
                "date_iso": end_dt.strftime("%Y-%m-%d"),
                "literal": None,
                "confidence": 0.80,
                "evidence": {
                    "page": page,
                    "bbox": None,
                    "snippet": f"afastado(a) por {dur} dia(s), a partir desta data",
                    "source_path": "layer2.texto_ocr_literal.valor",
                    "provenance_status": "inferred",
                },
            }

        result["afastamento"] = afastamento

    return result


def _determine_document_type(dm: DocumentMemory, page_items: List[Dict[str, Any]], text: str) -> str:
    text_upper = (text or "").upper()

    if ("ATESTADO" in text_upper and "CID" in text_upper) or ("ATESTADO" in text_upper and "CRM" in text_upper):
        return "atestado_medico"

    if "PARECER" in text_upper and "CRM" in text_upper:
        return "parecer_medico"

    if "RECEITU" in text_upper:
        return "receituario"

    if dm.layer3 and getattr(dm.layer3, "tipo_documento", None):
        valor = getattr(dm.layer3.tipo_documento, "valor", None)
        if valor and valor != "identidade":
            return valor

    ranked = sorted(page_items, key=_page_rank)
    for page_item in ranked:
        taxonomy = (page_item.get("page_taxonomy") or {}).get("value")
        if taxonomy:
            return taxonomy

    return "documento_composto"


def _quality_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    missing: List[str] = []
    warnings: List[str] = []

    if not payload.get("patient"):
        missing.append("patient")
    if not payload.get("provider"):
        missing.append("provider")
    if not payload.get("document_date"):
        missing.append("document_date")
    if not (payload.get("clinical") or {}).get("cids"):
        missing.append("clinical.cids")

    patient = payload.get("patient") or {}
    provider = payload.get("provider") or {}
    document_date = payload.get("document_date") or {}
    clinical = payload.get("clinical") or {}

    patient_ev = patient.get("evidence") or {}
    provider_ev = provider.get("evidence") or {}
    date_ev = document_date.get("evidence") or {}

    if patient and not patient_ev.get("bbox"):
        warnings.append("patient_without_exact_bbox")
    if provider and not provider_ev.get("bbox"):
        warnings.append("provider_without_exact_bbox")
    if document_date and not date_ev.get("bbox"):
        warnings.append("document_date_without_exact_bbox")

    pname = str(patient.get("name") or "")
    if not _looks_like_patient_name(pname, patient_ev.get("snippet")):
        warnings.append("implausible_patient_name")

    dsnip = str(date_ev.get("snippet") or "").lower()
    if any(x in dsnip for x in ("nascimento", "nascto", "idade")):
        warnings.append("document_date_looks_like_birth_date")

    if provider and not provider.get("crm"):
        warnings.append("provider_without_crm")

    for cid in clinical.get("cids") or []:
        ev = cid.get("evidence") or {}
        if ev.get("page") is None:
            warnings.append("cid_without_page_evidence")
            break

    has_minimum = (
        len(missing) <= 1
        and "implausible_patient_name" not in warnings
        and "document_date_looks_like_birth_date" not in warnings
    )

    return {
        "has_minimum_entities": has_minimum,
        "missing_critical_fields": missing,
        "warnings": list(dict.fromkeys(warnings)),
    }


def _layout_spans_for_pages(
    layout_spans: List[Dict[str, Any]],
    page_numbers: List[int],
) -> List[Dict[str, Any]]:
    page_set = {int(page) for page in page_numbers}
    return [
        span
        for span in layout_spans or []
        if isinstance(span, dict) and int(span.get("page") or 0) in page_set
    ]


def _normalize_relation_name(value: Optional[str]) -> Optional[str]:
    cleaned = _normalize_spaces(value)
    if not cleaned:
        return None
    return re.sub(r"[^a-z0-9]+", "", cleaned.lower())


def _parse_iso_date(value: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except Exception:
        return None


def _dedup_candidate_values(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        key = (
            candidate.get("value"),
            candidate.get("page_index"),
            json.dumps(candidate.get("evidence_ref") or {}, sort_keys=True, ensure_ascii=False),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    return out


def _dedup_evidence_refs(refs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        key = (
            ref.get("page"),
            ref.get("bbox") and tuple(ref.get("bbox")),
            ref.get("snippet"),
            ref.get("source_path"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(ref)
    return out


def _document_type_candidate(page_item: Dict[str, Any], document_type: Optional[str]) -> List[Dict[str, Any]]:
    taxonomy = (page_item.get("page_taxonomy") or {}).get("value")
    value = document_type or taxonomy
    if not value:
        return []
    confidence = 0.88 if taxonomy == value else 0.78
    return [
        {
            "value": value,
            "confidence": confidence,
            "review_state": "review_recommended" if confidence < 0.95 else "auto_confirmed",
            "assertion_level": "inferred",
            "page_index": int(page_item.get("page") or 0),
            "evidence_ref": {
                "page": int(page_item.get("page") or 0),
                "bbox": None,
                "snippet": str(page_item.get("page_text") or "")[:180],
                "source_path": "layer2.sinais_documentais.page_evidence_v1",
                "provenance_status": "inferred",
            },
        }
    ]


def _candidate_entries_from_legacy(
    field_name: str,
    legacy: Optional[Dict[str, Any]],
    *,
    value_key: str = "name",
) -> List[Dict[str, Any]]:
    if not isinstance(legacy, dict) or not legacy.get(value_key):
        return []
    evidence = legacy.get("evidence") or {}
    return [
        {
            "field": field_name,
            "value": legacy.get(value_key),
            "confidence": float(legacy.get("confidence") or 0.0),
            "review_state": legacy.get("review_state") or "review_recommended",
            "assertion_level": legacy.get("assertion_level") or _assertion_level_from_evidence(evidence),
            "page_index": evidence.get("page"),
            "evidence_ref": evidence,
        }
    ]


def _cid_candidates_from_clinical(clinical: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in (clinical.get("cids") or []):
        if not isinstance(item, dict) or not item.get("code"):
            continue
        evidence = item.get("evidence") or {}
        out.append(
            {
                "field": "cid",
                "value": item.get("code"),
                "confidence": 0.95 if evidence.get("bbox") else 0.78,
                "review_state": "auto_confirmed" if evidence.get("bbox") else "review_recommended",
                "assertion_level": item.get("assertion_level") or _assertion_level_from_evidence(evidence),
                "page_index": evidence.get("page"),
                "evidence_ref": evidence,
            }
        )
    return out


def _evidence_refs_from_page_item(page_item: Dict[str, Any]) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    for collection_name in ("anchors", "signal_zones"):
        for item in (page_item.get(collection_name) or []):
            if not isinstance(item, dict):
                continue
            refs.append(
                {
                    "page": item.get("page") or page_item.get("page"),
                    "bbox": item.get("bbox"),
                    "snippet": item.get("snippet"),
                    "source_path": item.get("source_path") or "layer2.sinais_documentais.page_evidence_v1",
                    "provenance_status": item.get("provenance_status") or ("exact" if item.get("bbox") else "unknown"),
                    "review_state": item.get("review_state"),
                    "confidence": item.get("confidence"),
                    "label": item.get("label"),
                    "value": item.get("value"),
                }
            )
    return _dedup_evidence_refs(refs)


def _uncertainties_from_payload(payload: Dict[str, Any]) -> List[str]:
    uncertainties: List[str] = []
    patient = payload.get("patient") or {}
    provider = payload.get("provider") or {}
    document_date = payload.get("document_date") or {}

    if not patient:
        uncertainties.append("patient_unknown")
    elif patient.get("review_state") != "auto_confirmed":
        uncertainties.append("patient_needs_review")

    if not provider:
        uncertainties.append("provider_unknown")
    elif provider.get("review_state") != "auto_confirmed":
        uncertainties.append("provider_needs_review")

    if not document_date:
        uncertainties.append("document_date_unknown")
    elif document_date.get("review_state") != "auto_confirmed":
        uncertainties.append("document_date_needs_review")

    if not (payload.get("clinical") or {}).get("cids"):
        uncertainties.append("cid_unknown")

    return list(dict.fromkeys(uncertainties))


def _confidence_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    patient_conf = float(((payload.get("patient") or {}).get("confidence") or 0.0))
    provider_conf = float(((payload.get("provider") or {}).get("confidence") or 0.0))
    document_date_conf = float(((payload.get("document_date") or {}).get("confidence") or 0.0))
    cid_scores = []
    for cid in ((payload.get("clinical") or {}).get("cids") or []):
        evidence = cid.get("evidence") or {}
        cid_scores.append(0.95 if evidence.get("bbox") else 0.78)
    present_scores = [score for score in (patient_conf, provider_conf, document_date_conf, max(cid_scores) if cid_scores else 0.0) if score > 0]
    overall = round(sum(present_scores) / len(present_scores), 3) if present_scores else 0.0
    return {
        "overall": overall,
        "patient": patient_conf or None,
        "provider": provider_conf or None,
        "document_date": document_date_conf or None,
        "cid": max(cid_scores) if cid_scores else None,
    }


def _build_page_unit_v1(
    dm: DocumentMemory,
    page_item: Dict[str, Any],
    layout_spans: List[Dict[str, Any]],
) -> Dict[str, Any]:
    page_index = int(page_item.get("page") or 0)
    payload = _build_canonical_from_page_items(
        [page_item],
        dm=dm,
        layout_spans=_layout_spans_for_pages(layout_spans, [page_index]),
        text=str(page_item.get("page_text") or ""),
    )
    warnings = list(dict.fromkeys((payload.get("quality") or {}).get("warnings") or []))
    uncertainties = _uncertainties_from_payload(payload)
    return {
        "page_index": page_index,
        "subdoc_id": page_item.get("subdoc_id"),
        "document_type": payload.get("document_type"),
        "document_type_candidates": _document_type_candidate(page_item, payload.get("document_type")),
        "patient": payload.get("patient"),
        "patient_candidates": _candidate_entries_from_legacy("patient", payload.get("patient")),
        "provider": payload.get("provider"),
        "provider_candidates": _candidate_entries_from_legacy("provider", payload.get("provider")),
        "document_date": payload.get("document_date"),
        "date_candidates": _candidate_entries_from_legacy("document_date", payload.get("document_date"), value_key="date_iso"),
        "clinical": payload.get("clinical") or {},
        "cid_candidates": _cid_candidates_from_clinical(payload.get("clinical") or {}),
        "evidence_refs": _evidence_refs_from_page_item(page_item),
        "confidence": _confidence_summary(payload),
        "warnings": warnings,
        "uncertainties": uncertainties,
    }


def _build_subdocument_unit_v1(
    subdoc_id: str,
    page_units: List[Dict[str, Any]],
    canonical_payload: Dict[str, Any],
    subdocument_source: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    pages = sorted(
        {
            int(page)
            for page in (
                ((subdocument_source or {}).get("page_map") or [])
                and [
                    item.get("page")
                    for item in (subdocument_source or {}).get("page_map") or []
                    if isinstance(item, dict) and item.get("page") is not None
                ]
                or [item.get("page_index") for item in page_units]
            )
            if page is not None
        }
    )
    evidence_refs = _dedup_evidence_refs(
        [ref for unit in page_units for ref in (unit.get("evidence_refs") or [])]
    )
    warnings = list(
        dict.fromkeys(
            (canonical_payload.get("quality") or {}).get("warnings") or []
            + [warning for unit in page_units for warning in (unit.get("warnings") or [])]
        )
    )
    uncertainties = list(
        dict.fromkeys(
            _uncertainties_from_payload(canonical_payload)
            + [item for unit in page_units for item in (unit.get("uncertainties") or [])]
        )
    )
    return {
        "subdoc_id": subdoc_id,
        "pages": pages,
        "page_units": [unit.get("page_index") for unit in sorted(page_units, key=lambda item: item.get("page_index") or 0)],
        "document_type": canonical_payload.get("document_type"),
        "document_type_candidates": _dedup_candidate_values(
            [candidate for unit in page_units for candidate in (unit.get("document_type_candidates") or [])]
        ),
        "patient": canonical_payload.get("patient"),
        "patient_candidates": _dedup_candidate_values(
            [candidate for unit in page_units for candidate in (unit.get("patient_candidates") or [])]
        ),
        "provider": canonical_payload.get("provider"),
        "provider_candidates": _dedup_candidate_values(
            [candidate for unit in page_units for candidate in (unit.get("provider_candidates") or [])]
        ),
        "document_date": canonical_payload.get("document_date"),
        "date_candidates": _dedup_candidate_values(
            [candidate for unit in page_units for candidate in (unit.get("date_candidates") or [])]
        ),
        "clinical": canonical_payload.get("clinical") or {},
        "cid_candidates": _dedup_candidate_values(
            [candidate for unit in page_units for candidate in (unit.get("cid_candidates") or [])]
        ),
        "internacao": canonical_payload.get("internacao"),
        "afastamento": canonical_payload.get("afastamento"),
        "evidence_refs": evidence_refs,
        "confidence": _confidence_summary(canonical_payload),
        "warnings": warnings,
        "uncertainties": uncertainties,
    }


def _relation_edge(
    relation_type: str,
    source_subdoc_id: str,
    target_subdoc_id: str,
    *,
    confidence: float,
    reasons: List[str],
    evidence_refs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "relation_type": relation_type,
        "source_subdoc_id": source_subdoc_id,
        "target_subdoc_id": target_subdoc_id,
        "confidence": confidence,
        "reasons": reasons,
        "evidence_refs": _dedup_evidence_refs(evidence_refs),
    }


def _build_document_relation_graph_v1(subdocument_units: List[Dict[str, Any]]) -> Dict[str, Any]:
    nodes = [
        {
            "subdoc_id": unit.get("subdoc_id"),
            "pages": unit.get("pages") or [],
            "document_type": unit.get("document_type"),
            "patient": ((unit.get("patient") or {}).get("name")),
            "provider": ((unit.get("provider") or {}).get("name")),
            "document_date": ((unit.get("document_date") or {}).get("date_iso")),
            "warnings": unit.get("warnings") or [],
            "uncertainties": unit.get("uncertainties") or [],
        }
        for unit in subdocument_units
    ]

    edges: List[Dict[str, Any]] = []
    for index, left in enumerate(subdocument_units):
        for right in subdocument_units[index + 1 :]:
            left_patient = _normalize_relation_name(((left.get("patient") or {}).get("name")))
            right_patient = _normalize_relation_name(((right.get("patient") or {}).get("name")))
            left_provider = _normalize_relation_name(((left.get("provider") or {}).get("name")))
            right_provider = _normalize_relation_name(((right.get("provider") or {}).get("name")))
            left_date = ((left.get("document_date") or {}).get("date_iso"))
            right_date = ((right.get("document_date") or {}).get("date_iso"))
            left_dt = _parse_iso_date(left_date)
            right_dt = _parse_iso_date(right_date)
            left_type = left.get("document_type")
            right_type = right.get("document_type")
            left_cids = {item.get("code") for item in ((left.get("clinical") or {}).get("cids") or []) if isinstance(item, dict) and item.get("code")}
            right_cids = {item.get("code") for item in ((right.get("clinical") or {}).get("cids") or []) if isinstance(item, dict) and item.get("code")}
            pair_refs = (left.get("evidence_refs") or [])[:2] + (right.get("evidence_refs") or [])[:2]

            if left_patient and right_patient and left_patient == right_patient:
                edges.append(
                    _relation_edge(
                        "same_patient",
                        left["subdoc_id"],
                        right["subdoc_id"],
                        confidence=0.97,
                        reasons=["patient_name_match"],
                        evidence_refs=pair_refs,
                    )
                )

            if left_provider and right_provider and left_provider == right_provider:
                edges.append(
                    _relation_edge(
                        "same_provider",
                        left["subdoc_id"],
                        right["subdoc_id"],
                        confidence=0.95,
                        reasons=["provider_name_match"],
                        evidence_refs=pair_refs,
                    )
                )

            if left_patient and right_patient and left_patient == right_patient:
                same_episode = False
                reasons: List[str] = []
                if left_dt and right_dt and abs((left_dt - right_dt).days) <= 30:
                    same_episode = True
                    reasons.append("document_dates_within_30_days")
                if left_cids and right_cids and left_cids.intersection(right_cids):
                    same_episode = True
                    reasons.append("cid_overlap")
                if same_episode:
                    edges.append(
                        _relation_edge(
                            "same_episode",
                            left["subdoc_id"],
                            right["subdoc_id"],
                            confidence=0.9,
                            reasons=reasons,
                            evidence_refs=pair_refs,
                        )
                    )

            if (
                left_patient
                and right_patient
                and left_patient == right_patient
                and left_provider
                and right_provider
                and left_provider == right_provider
                and left_type
                and left_type == right_type
                and left_date
                and left_date == right_date
            ):
                edges.append(
                    _relation_edge(
                        "same_document_continuation",
                        left["subdoc_id"],
                        right["subdoc_id"],
                        confidence=0.94,
                        reasons=["same_patient_provider_type_and_date"],
                        evidence_refs=pair_refs,
                    )
                )

            if (
                left_patient
                and right_patient
                and left_patient != right_patient
                and (
                    (left_provider and right_provider and left_provider == right_provider)
                    or (left_type and right_type and left_type == right_type and left_date and left_date == right_date)
                )
            ):
                edges.append(
                    _relation_edge(
                        "conflict",
                        left["subdoc_id"],
                        right["subdoc_id"],
                        confidence=0.98,
                        reasons=["patient_mismatch_under_shared_context"],
                        evidence_refs=pair_refs,
                    )
                )

            if not any(
                edge["source_subdoc_id"] == left["subdoc_id"] and edge["target_subdoc_id"] == right["subdoc_id"]
                for edge in edges
            ):
                if (
                    not left_patient
                    or not right_patient
                    or not left_provider
                    or not right_provider
                    or not left_date
                    or not right_date
                ):
                    edges.append(
                        _relation_edge(
                            "unknown",
                            left["subdoc_id"],
                            right["subdoc_id"],
                            confidence=0.35,
                            reasons=["insufficient_shared_evidence"],
                            evidence_refs=pair_refs,
                        )
                    )

    relation_counts: Dict[str, int] = {}
    for edge in edges:
        relation_counts[edge["relation_type"]] = relation_counts.get(edge["relation_type"], 0) + 1

    return {
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "subdocument_count": len(nodes),
            "edge_count": len(edges),
            "relation_counts": relation_counts,
        },
    }


def _build_canonical_from_page_items(
    page_items: List[Dict[str, Any]],
    *,
    dm: Optional[DocumentMemory] = None,
    layout_spans: Optional[List[Dict[str, Any]]] = None,
    text: Optional[str] = None,
) -> Dict[str, Any]:
    safe_page_items = [item for item in page_items if isinstance(item, dict)]
    safe_layout_spans = layout_spans or []
    safe_text = text if text is not None else "\n\n".join(
        str(item.get("page_text") or "") for item in safe_page_items
    )

    document_type = _determine_document_type(dm, safe_page_items, safe_text) if dm else "documento_composto"
    people_resolution = _PEOPLE_RESOLVER.resolve(safe_page_items, safe_layout_spans, {})
    document_date_resolution = _DOCUMENT_DATE_RESOLVER.resolve(safe_page_items, safe_layout_spans, {})

    payload: Dict[str, Any] = {
        "document_type": document_type,
        "patient": _person_resolution_to_legacy(people_resolution.get("patient")),
        "mother": _person_resolution_to_legacy(people_resolution.get("mother")),
        "provider": _person_resolution_to_legacy(people_resolution.get("provider")),
        "clinical": _pick_clinical(safe_page_items, safe_text),
        "document_date": _document_date_resolution_to_legacy(document_date_resolution),
        "semantic_resolution_v1": {
            "people": people_resolution,
            "document_date": document_date_resolution,
        },
        "_debug_doc_type_decision": {
            "final_document_type": document_type,
            "text_has_atestado": bool(_RE_ATTESTADO.search(safe_text or "")),
            "text_has_cid": bool(_RE_CID.search(safe_text or "")),
            "text_has_crm": bool(_RE_CRM.search(safe_text or "")),
            "text_has_internado": bool(_RE_INTERNADO.search(safe_text or "")),
            "page_count_considered": len(safe_page_items),
        },
    }

    if document_type == "atestado_medico":
        ranked = sorted(safe_page_items, key=_page_rank)
        page_item = ranked[0] if ranked else {"page": 1}
        payload.update(_parse_internacao_afastamento(safe_text, page_item))

    payload["quality"] = _quality_report(payload)
    return payload


def apply_entities_canonical_v1(dm: DocumentMemory) -> DocumentMemory:
    if dm.layer2 is None:
        return dm

    page_items = _all_page_evidence(dm)
    layout_spans = _load_signal_json(dm, "layout_spans_v1") or []
    subdocuments_signal = _load_signal_json(dm, "subdocuments_v1") or []
    text = _safe_text(dm)
    payload = _build_canonical_from_page_items(
        page_items,
        dm=dm,
        layout_spans=layout_spans,
        text=text,
    )

    page_units = [
        _build_page_unit_v1(dm, page_item, layout_spans)
        for page_item in sorted(page_items, key=lambda item: int(item.get("page") or 999999))
        if isinstance(page_item, dict) and page_item.get("page") is not None
    ]

    subdocuments: List[Dict[str, Any]] = []
    subdocument_units: List[Dict[str, Any]] = []
    for subdoc_id, subdoc_page_items in _group_page_items_by_subdoc(page_items):
        if subdoc_id == "__document__":
            continue
        subdoc_text = "\n\n".join(
            str(item.get("page_text") or "") for item in subdoc_page_items
        )
        subdoc_payload = _build_canonical_from_page_items(
            subdoc_page_items,
            dm=dm,
            layout_spans=layout_spans,
            text=subdoc_text,
        )
        subdoc_payload["subdoc_id"] = subdoc_id
        subdoc_payload["pages"] = [
            int(item.get("page"))
            for item in sorted(subdoc_page_items, key=lambda item: int(item.get("page") or 999999))
            if item.get("page") is not None
        ]
        subdocuments.append(subdoc_payload)
        source_subdoc = next(
            (
                item
                for item in subdocuments_signal
                if isinstance(item, dict) and item.get("subdoc_id") == subdoc_id
            ),
            None,
        )
        subdocument_units.append(
            _build_subdocument_unit_v1(
                subdoc_id,
                [unit for unit in page_units if unit.get("subdoc_id") == subdoc_id],
                subdoc_payload,
                source_subdoc,
            )
        )

    if subdocuments:
        payload["subdocuments"] = subdocuments
        payload["aggregate_projection_v1"] = {
            "mode": "compatibility_aggregate",
            "status": "temporary",
            "authoritative_source": "subdocuments",
            "subdocument_count": len(subdocuments),
            "derived_fields": [
                "document_type",
                "patient",
                "mother",
                "provider",
                "clinical",
                "document_date",
            ],
        }

    relation_graph = _build_document_relation_graph_v1(subdocument_units) if subdocument_units else {
        "nodes": [],
        "edges": [],
        "summary": {"subdocument_count": 0, "edge_count": 0, "relation_counts": {}},
    }

    dm = _make_signal(dm, "page_unit_v1", page_units, "epistemic_page_segmentation_v1")
    dm = _make_signal(dm, "subdocument_unit_v1", subdocument_units, "epistemic_subdocument_segmentation_v1")
    dm = _make_signal(dm, "document_relation_graph_v1", relation_graph, "document_relation_graph_v1")
    dm = _make_signal(dm, "entities_canonical_v1", payload, "consolidation_v4_multi_page_semantic")
    return apply_legal_canonical_fields_v1(dm, canonical=payload)
