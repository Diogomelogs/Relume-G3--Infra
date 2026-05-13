
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.types_basic import ProvenancedString
from relluna.services.evidence.signals import load_critical_signal_json

FONTE = "deterministic_extractors.entities_hard_v2"

_RE_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b")
_RE_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
_RE_DATE_NUMERIC = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
_RE_DATE_TEXTUAL = re.compile(
    r"\b(\d{1,2})\s+de\s+([A-Za-zçÇãÃáàâéêíóôõú]+)\s+de\s+(\d{4})\b",
    re.IGNORECASE,
)
_RE_MONEY = re.compile(r"R\$\s*([\d\.\,]+)")
_RE_CID = re.compile(r"\b([A-TV-Z][0-9]{2}(?:\.[0-9A-Z]{1,2})?)\b")
_RE_CRM = re.compile(r"\bCRM(?:\s*[-:/]?\s*[A-Z]{0,2})?\s*[-:]?\s*(\d{4,8})\b", re.IGNORECASE)
_RE_AFASTAMENTO_DIAS = re.compile(
    r"(?:afastad[oa].{0,50}?por\s+|repouso\s+de\s+)(\d{1,3})\s*dias",
    re.IGNORECASE | re.DOTALL,
)
_RE_INTERNADO_PERIODO = re.compile(
    r"internad[oa].{0,80}?do dia\s+(\d{2}/\d{2}/\d{4}).{0,40}?ao dia\s+(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE | re.DOTALL,
)

_MONTHS_PT = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}

_CID_CONTEXT_POSITIVE = (
    "cid", "diagnostico", "diagnóstico", "hipotese", "hipótese", "transtorno",
    "quadro", "depress", "ansiedade", "quadro clinico", "quadro clínico",
    "encaminhamento", "parecer", "atestado", "internado", "afastado", "motivo",
)
_CID_CONTEXT_NEGATIVE = (
    "rua", "avenida", "andar", "bairro", "cep", "sao paulo", "são paulo",
    "campinas", "guarulhos", "osasco", "tatuape", "tatuapé", "vila", "centro",
    "endereco", "endereço", "logradouro", "uf",
)

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

def _validate_cpf(cpf: str) -> bool:
    numbers = re.sub(r"\D", "", cpf)
    if len(numbers) != 11 or numbers == numbers[0] * 11:
        return False
    def calc_digit(n: str) -> int:
        s = sum(int(n[i]) * ((len(n) + 1) - i) for i in range(len(n)))
        d = (s * 10) % 11
        return 0 if d == 10 else d
    return calc_digit(numbers[:9]) == int(numbers[9]) and calc_digit(numbers[:10]) == int(numbers[10])

def _validate_cnpj(cnpj: str) -> bool:
    numbers = re.sub(r"\D", "", cnpj)
    if len(numbers) != 14:
        return False
    def calc_digit(n: str, weights: List[int]) -> int:
        s = sum(int(n[i]) * weights[i] for i in range(len(weights)))
        r = s % 11
        return 0 if r < 2 else 11 - r
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6] + weights1
    return calc_digit(numbers[:12], weights1) == int(numbers[12]) and calc_digit(numbers[:13], weights2) == int(numbers[13])

def _parse_date_literal(raw: str) -> Optional[str]:
    raw = (raw or "").strip()
    m = _RE_DATE_NUMERIC.fullmatch(raw)
    if m:
        d, mo, y = m.groups()
        try:
            return datetime(int(y), int(mo), int(d)).strftime("%Y-%m-%d")
        except ValueError:
            return None
    m = _RE_DATE_TEXTUAL.fullmatch(raw)
    if m:
        d, month_name, y = m.groups()
        month = _MONTHS_PT.get(month_name.strip().lower())
        if not month:
            return None
        try:
            return datetime(int(y), month, int(d)).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None

def _cid_context_ok(text: str, start: int, end: int) -> bool:
    lo = max(0, start - 120)
    hi = min(len(text), end + 120)
    ctx = text[lo:hi].lower()
    line_lo = text.rfind("\n", 0, start)
    line_hi = text.find("\n", end)
    line_lo = 0 if line_lo == -1 else line_lo + 1
    line_hi = len(text) if line_hi == -1 else line_hi
    line_ctx = text[line_lo:line_hi].lower()
    if any(term in line_ctx for term in _CID_CONTEXT_NEGATIVE):
        return False
    if any(term in ctx for term in _CID_CONTEXT_NEGATIVE) and not any(term in ctx for term in _CID_CONTEXT_POSITIVE):
        return False
    if any(term in line_ctx for term in _CID_CONTEXT_POSITIVE):
        return True
    if any(term in ctx for term in _CID_CONTEXT_POSITIVE):
        return True
    return False

def _find_anchor_for_value(page_evidence: List[Dict[str, Any]], label: str, value: str) -> Tuple[Optional[int], Optional[List[float]], Optional[str], Optional[float]]:
    value_norm = str(value or "").strip().lower()
    if not value_norm:
        return None, None, None, None
    best = None
    for page in page_evidence:
        for anchor in page.get("anchors") or []:
            if str(anchor.get("label") or "").strip().lower() != label.lower():
                continue
            anchor_value = str(anchor.get("value") or "").strip().lower()
            if anchor_value == value_norm:
                confidence = anchor.get("confidence")
                if confidence is None:
                    confidence = 0.97 if anchor.get("bbox") else 0.84
                return anchor.get("page"), anchor.get("bbox"), anchor.get("snippet"), confidence
            if value_norm in anchor_value or anchor_value in value_norm:
                best = best or (
                    anchor.get("page"),
                    anchor.get("bbox"),
                    anchor.get("snippet"),
                    anchor.get("confidence") if anchor.get("confidence") is not None else (0.97 if anchor.get("bbox") else 0.84),
                )
    return best or (None, None, None, None)

def _find_person(page_evidence: List[Dict[str, Any]], key: str) -> Optional[Dict[str, Any]]:
    best = None
    for page in page_evidence:
        people = page.get("people") or {}
        value = people.get(key)
        if not value:
            continue
        conf = people.get(key.replace("_name", "_confidence"), 0.75)
        page_no, bbox, snippet, anchor_conf = _find_anchor_for_value(page_evidence, key, value)
        out = {
            "type": key,
            "value": value,
            "page": page_no or page.get("page"),
            "bbox": bbox,
            "snippet": snippet or value,
            "confidence": max(conf, anchor_conf or 0),
        }
        if best is None or out["confidence"] > best["confidence"]:
            best = out
    return best

def _append_unique(rows: List[Dict[str, Any]], item: Dict[str, Any], key_fields: List[str]) -> None:
    key = tuple(item.get(k) for k in key_fields)
    for row in rows:
        if tuple(row.get(k) for k in key_fields) == key:
            return
    rows.append(item)

def extract_hard_entities_v2(dm: DocumentMemory) -> DocumentMemory:
    if dm.layer2 is None or dm.layer2.texto_ocr_literal is None:
        return dm

    text = dm.layer2.texto_ocr_literal.valor or ""
    page_evidence = _load_signal_json(dm, "page_evidence_v1") or []
    results: List[Dict[str, Any]] = []

    patient = _find_person(page_evidence, "patient_name")
    if patient:
        _append_unique(results, patient, ["type", "value"])

    mother = _find_person(page_evidence, "mother_name")
    if mother:
        _append_unique(results, mother, ["type", "value"])

    provider = _find_person(page_evidence, "provider_name")
    if provider:
        provider["type"] = "provider_name"
        _append_unique(results, provider, ["type", "value"])

    for raw in _RE_CPF.findall(text):
        digits = re.sub(r"\D", "", raw)
        if not _validate_cpf(digits):
            continue
        page, bbox, snippet, confidence = _find_anchor_for_value(page_evidence, "cpf", digits)
        _append_unique(results, {
            "type": "cpf",
            "value": digits,
            "page": page,
            "bbox": bbox,
            "snippet": snippet or raw,
            "confidence": confidence or 0.95,
        }, ["type", "value"])

    for raw in _RE_CNPJ.findall(text):
        if not _validate_cnpj(raw):
            continue
        page, bbox, snippet, confidence = _find_anchor_for_value(page_evidence, "cnpj", raw)
        _append_unique(results, {
            "type": "cnpj",
            "value": raw,
            "page": page,
            "bbox": bbox,
            "snippet": snippet or raw,
            "confidence": confidence or 0.95,
        }, ["type", "value"])

    for m in _RE_CRM.finditer(text):
        crm = m.group(1)
        page, bbox, snippet, confidence = _find_anchor_for_value(page_evidence, "crm", crm)
        _append_unique(results, {
            "type": "crm",
            "value": crm,
            "page": page,
            "bbox": bbox,
            "snippet": snippet or m.group(0),
            "confidence": confidence or 0.92,
        }, ["type", "value"])

    for m in _RE_CID.finditer(text):
        cid = m.group(1)
        if not _cid_context_ok(text, m.start(), m.end()):
            continue
        page, bbox, snippet, confidence = _find_anchor_for_value(page_evidence, "cid", cid)
        _append_unique(results, {
            "type": "cid",
            "value": cid,
            "page": page,
            "bbox": bbox,
            "snippet": snippet or cid,
            "confidence": confidence or 0.95,
        }, ["type", "value"])

    for match in _RE_MONEY.findall(text):
        value_float = float(match.replace(".", "").replace(",", "."))
        _append_unique(results, {
            "type": "valor_monetario",
            "value_literal": match,
            "value_float": value_float,
        }, ["type", "value_literal"])

    # page-derived dates with roles
    for page in page_evidence:
        people = page.get("people") or {}
        admin = page.get("administrative_entities") or {}
        clinical = page.get("clinical_entities") or {}
        date_candidates = page.get("date_candidates") or []

        birth_date = admin.get("birth_date") if isinstance(admin, dict) else None
        if birth_date:
            iso = _parse_date_literal(birth_date)
            if iso:
                page_no, bbox, snippet, confidence = _find_anchor_for_value(page_evidence, "date", birth_date)
                _append_unique(results, {
                    "type": "date",
                    "role": "birth_date",
                    "value_literal": birth_date,
                    "value_iso": iso,
                    "page": page_no or page.get("page"),
                    "bbox": bbox,
                    "snippet": snippet or birth_date,
                    "confidence": confidence or 0.9,
                }, ["type", "role", "value_iso"])

        attendance = clinical.get("attendance") if isinstance(clinical, dict) else None
        if attendance and attendance.get("date"):
            raw = attendance["date"]
            iso = _parse_date_literal(raw)
            if iso:
                page_no, bbox, snippet, confidence = _find_anchor_for_value(page_evidence, "date", raw)
                _append_unique(results, {
                    "type": "date",
                    "role": "attendance_date",
                    "value_literal": raw,
                    "value_iso": iso,
                    "page": page_no or page.get("page"),
                    "bbox": bbox,
                    "snippet": snippet or raw,
                    "confidence": confidence or 0.95,
                }, ["type", "role", "value_iso"])

        for dc in date_candidates:
            raw = dc.get("literal")
            iso = dc.get("date_iso") or _parse_date_literal(raw or "")
            if not raw or not iso:
                continue
            page_no, bbox, snippet, confidence = _find_anchor_for_value(page_evidence, "date", raw)
            role = "document_date_candidate"
            snippet_l = (snippet or raw).lower()

            if "nascimento" in (page.get("page_text") or "").lower() and raw in (page.get("page_text") or ""):
                role = "birth_date"
            elif "são paulo" in snippet_l or "sao paulo" in snippet_l:
                role = "document_issue_date"

            _append_unique(results, {
                "type": "date",
                "role": role,
                "value_literal": raw,
                "value_iso": iso,
                "page": page_no or page.get("page"),
                "bbox": bbox,
                "snippet": snippet or raw,
                "confidence": confidence or (0.97 if bbox else 0.84),
            }, ["type", "role", "value_iso", "page"])

    # internacao range
    for m in _RE_INTERNADO_PERIODO.finditer(text):
        start_raw, end_raw = m.groups()
        start_iso = _parse_date_literal(start_raw)
        end_iso = _parse_date_literal(end_raw)
        if start_iso:
            page, bbox, snippet, confidence = _find_anchor_for_value(page_evidence, "date", start_raw)
            _append_unique(results, {
                "type": "date",
                "role": "internacao_inicio",
                "value_literal": start_raw,
                "value_iso": start_iso,
                "page": page,
                "bbox": bbox,
                "snippet": snippet or m.group(0),
                "confidence": confidence or 0.97,
            }, ["type", "role", "value_iso"])
        if end_iso:
            page, bbox, snippet, confidence = _find_anchor_for_value(page_evidence, "date", end_raw)
            _append_unique(results, {
                "type": "date",
                "role": "internacao_fim",
                "value_literal": end_raw,
                "value_iso": end_iso,
                "page": page,
                "bbox": bbox,
                "snippet": snippet or m.group(0),
                "confidence": confidence or 0.97,
            }, ["type", "role", "value_iso"])

    # afastamento days from document issue
    issue_dates = [r for r in results if r.get("type") == "date" and r.get("role") == "document_issue_date"]
    attendance_dates = [r for r in results if r.get("type") == "date" and r.get("role") == "attendance_date"]
    base_date = None
    if issue_dates:
        base_date = issue_dates[0]["value_iso"]
    elif attendance_dates:
        base_date = attendance_dates[0]["value_iso"]

    for m in _RE_AFASTAMENTO_DIAS.finditer(text):
        days = int(m.group(1))
        if not base_date:
            continue
        start_dt = datetime.fromisoformat(base_date)
        end_dt = start_dt + timedelta(days=days)
        _append_unique(results, {
            "type": "date",
            "role": "afastamento_inicio",
            "value_literal": base_date,
            "value_iso": base_date,
            "confidence": 0.86,
            "snippet": m.group(0),
        }, ["type", "role", "value_iso"])
        _append_unique(results, {
            "type": "date",
            "role": "afastamento_fim_estimado",
            "value_literal": end_dt.strftime("%d/%m/%Y"),
            "value_iso": end_dt.strftime("%Y-%m-%d"),
            "confidence": 0.78,
            "snippet": m.group(0),
        }, ["type", "role", "value_iso"])
        _append_unique(results, {
            "type": "duration_days",
            "role": "afastamento_dias",
            "value_int": days,
            "snippet": m.group(0),
            "confidence": 0.9,
        }, ["type", "role", "value_int"])

    if not results:
        return dm

    dm.layer2.sinais_documentais["hard_entities_v2"] = ProvenancedString(
        valor=json.dumps(results, ensure_ascii=False),
        fonte=FONTE,
        metodo="regex+page_evidence_roles_v5",
        estado="confirmado",
        confianca=1.0,
    )
    return dm
