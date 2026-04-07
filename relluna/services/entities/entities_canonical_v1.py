from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.types_basic import ProvenancedString

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


def _safe_text(dm: DocumentMemory) -> str:
    if dm.layer2 and dm.layer2.texto_ocr_literal and dm.layer2.texto_ocr_literal.valor:
        return dm.layer2.texto_ocr_literal.valor
    return ""


def _all_page_evidence(dm: DocumentMemory) -> List[Dict[str, Any]]:
    page_evidence = _load_signal_json(dm, "page_evidence_v1") or []
    if isinstance(page_evidence, list):
        return [x for x in page_evidence if isinstance(x, dict)]
    return []


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

    m = re.search(
        r"Paciente:\s*([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-Za-zÁÀÃÂÉÊÍÓÔÕÚÇáàãâéêíóôõúç\s]+)",
        text or "",
        re.IGNORECASE,
    )
    if m:
        candidate = _trim_header_field_noise(m.group(1))
        if _looks_like_patient_name(candidate):
            return candidate

    return None


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


def _looks_like_patient_name(value: Optional[str]) -> bool:
    value = _trim_header_field_noise(value)
    if not value:
        return False

    if not _looks_like_person(value):
        return False

    tokens = value.split()
    if len(tokens) < 3:
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

    if role_key == "patient_name" and not _looks_like_patient_name(name):
        return None
    if role_key == "mother_name" and not _looks_like_mother_name(name):
        return None
    if role_key == "provider_name" and not _looks_like_provider_name(name):
        return None

    confidence_key = role_key.replace("_name", "_confidence")
    review_key = role_key.replace("_name", "_review_state")
    conf = float(people.get(confidence_key) or 0.0)
    review = people.get(review_key) or "review_recommended"

    label_map = {
        "patient_name": "patient",
        "mother_name": "mother",
        "provider_name": "provider",
    }
    anchor = _best_anchor_for_label(page_item, label_map[role_key])

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

    birth_markers = [
        "nascimento",
        "nascto",
        "data de nascimento",
        "idade",
    ]
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

    if any(m in snippet_low for m in birth_markers):
        penalty -= 1.0

    # janela local aproximada
    idx = text_low.find(literal_low)
    if idx >= 0:
        left = max(0, idx - 80)
        right = min(len(text_low), idx + len(literal_low) + 80)
        window = text_low[left:right]

        if any(m in window for m in birth_markers):
            penalty -= 1.2
        if any(m in window for m in issue_markers):
            penalty += 0.45

    return penalty


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
    if not _looks_like_patient_name(pname):
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


def apply_entities_canonical_v1(dm: DocumentMemory) -> DocumentMemory:
    if dm.layer2 is None:
        return dm

    page_items = _all_page_evidence(dm)
    layout_spans = _load_signal_json(dm, "layout_spans_v1") or []
    text = _safe_text(dm)

    document_type = _determine_document_type(dm, page_items, text)

    payload: Dict[str, Any] = {
        "document_type": document_type,
        "patient": _pick_best_patient(page_items, text, layout_spans),
        "mother": _pick_best_mother(page_items),
        "provider": _pick_best_provider(page_items, text),
        "clinical": _pick_clinical(page_items, text),
        "document_date": _pick_document_date(page_items, text),
        "_debug_doc_type_decision": {
            "final_document_type": document_type,
            "text_has_atestado": bool(_RE_ATTESTADO.search(text or "")),
            "text_has_cid": bool(_RE_CID.search(text or "")),
            "text_has_crm": bool(_RE_CRM.search(text or "")),
            "text_has_internado": bool(_RE_INTERNADO.search(text or "")),
            "page_count_considered": len(page_items),
        },
    }

    if document_type == "atestado_medico":
        ranked = sorted(page_items, key=_page_rank)
        page_item = ranked[0] if ranked else {"page": 1}
        payload.update(_parse_internacao_afastamento(text, page_item))

    payload["quality"] = _quality_report(payload)

    return _make_signal(dm, "entities_canonical_v1", payload, "consolidation_v4_multi_page_semantic")