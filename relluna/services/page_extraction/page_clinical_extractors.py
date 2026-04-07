from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

RE_CID = re.compile(r"\b([A-TV-Z][0-9]{2}(?:\.[0-9A-Z]{1,2})?)\b")
RE_MEDICATION = re.compile(
    r"(?:\d+\)\s*)?([A-ZÁÀÃÂÉÊÍÓÔÕÚÇa-zà-ÿ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇa-zà-ÿ\s\-]{2,40}?)\s+(\d+(?:,\d+)?\s*(?:mg|mcg|g|ml))\b",
    re.IGNORECASE,
)
RE_POSOLOGY = re.compile(
    r"((?:tomar|usar|aplicar)\s+.+?)(?=\n\n|\n[A-Z]{2,}|$)",
    re.IGNORECASE | re.DOTALL,
)
RE_SPECIALTY = re.compile(
    r"especialidade[:;\s]+([A-Za-zÀ-ÿ\s]{3,}?)(?=\n|Prestador|Servico|Serviço|$)",
    re.IGNORECASE,
)
RE_PROVIDER = re.compile(
    r"prestador[:;\s]+([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇ\s]{5,}?)(?=\s+Servico[:;\s]|\s+Serviço[:;\s]|\s+Especialidade[:;\s]|\n|$)",
    re.IGNORECASE,
)
RE_SERVICE = re.compile(
    r"servi[cç]o[:;\s]+([A-Za-zÀ-ÿ\s]{3,}?)(?=\s+Especialidade[:;\s]|\n|$)",
    re.IGNORECASE,
)
RE_PRESCRIPTION_NUMBER = re.compile(r"\b01-\s*\d{6}\b")
RE_ATTENDANCE = re.compile(
    r"data/hora\s+atendimento[:;\s]+(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})",
    re.IGNORECASE,
)

FALSE_CID_CONTEXT = [
    "sao paulo",
    "s30 paulo",
]

RE_CITY_DATE_LINE = re.compile(
    r"^[A-ZÁÀÃÂÉÊÍÓÔÕÚÇa-zà-ÿ\s]+,\s*\d{1,2}\s+de\s+[A-ZÁÀÃÂÉÊÍÓÔÕÚÇa-zà-ÿ]+\s+de\s+\d{4}",
    re.IGNORECASE,
)
RE_PERSON_NAME = re.compile(
    r"^[A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][a-záàãâéêíóôõúç]+(?:\s+[A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][a-záàãâéêíóôõúç]+){1,5}$"
)
RE_CRM_LINE = re.compile(r"\bCRM\b", re.IGNORECASE)
RE_SPECIALTY_FALLBACK = re.compile(
    r"\b(m[eé]dico\s+cl[ií]nico|psiquiatr[aia]|psicolog[oa]|neurolog[iaa]|ortoped[iaa])\b",
    re.IGNORECASE,
)
RE_PROVIDER_INLINE = re.compile(
    r"\b(?:dr\.?|dra\.?)\s+([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-Za-zÁÀÃÂÉÊÍÓÔÕÚÇáàãâéêíóôõúç'\-]+(?:\s+[A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-Za-zÁÀÃÂÉÊÍÓÔÕÚÇáàãâéêíóôõúç'\-]+){1,5})",
    re.IGNORECASE,
)
RE_PROVIDER_CRM_INLINE = re.compile(
    r"([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-Za-zÁÀÃÂÉÊÍÓÔÕÚÇáàãâéêíóôõúç'\-]+(?:\s+[A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-Za-zÁÀÃÂÉÊÍÓÔÕÚÇáàãâéêíóôõúç'\-]+){1,5})\s*\(?CRM\s*[-:]?\s*\d{4,8}\)?",
    re.IGNORECASE,
)
RE_SPECIALTY_INLINE = re.compile(
    r"\b(cirurgia\s+geral|urologia|neurologia|ortopedia|psiquiatria|psicologia|cardiologia|cl[ií]nica\s+m[eé]dica)\b",
    re.IGNORECASE,
)


def _clean(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return " ".join(value.split()).strip(" |:;")


def _dedup_dicts(rows: List[Dict[str, Any]], key_fields: List[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        key = tuple(
            (row.get(k) or "").lower() if isinstance(row.get(k), str) else row.get(k)
            for k in key_fields
        )
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def _dedup_strings(values: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        cleaned = _clean(value)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


def _infer_provider_name_fallback(text: str) -> Optional[str]:
    text = text or ""

    m = RE_PROVIDER_CRM_INLINE.search(text)
    if m:
        candidate = _clean(m.group(1))
        if candidate:
            return candidate

    m = RE_PROVIDER_INLINE.search(text)
    if m:
        candidate = _clean(m.group(1))
        if candidate:
            return candidate

    lines = [l.strip() for l in text.splitlines() if l.strip()]

    for idx, line in enumerate(lines):
        if not RE_CRM_LINE.search(line):
            continue

        candidates: List[str] = []

        for j in range(max(0, idx - 3), min(len(lines), idx + 3)):
            raw = _clean(lines[j])
            if not raw:
                continue
            low = raw.lower()

            if RE_CITY_DATE_LINE.search(raw):
                continue
            if any(x in low for x in ["paciente", "mãe", "mae", "filiação", "filiacao", "cid", "motivo"]):
                continue
            if low in {"são paulo", "sao paulo"}:
                continue

            if RE_PERSON_NAME.fullmatch(raw):
                candidates.append(raw)

        if candidates:
            candidates.sort(
                key=lambda x: (
                    0 if x.lower().startswith(("dr ", "dra ", "dr.", "dra.")) else 1,
                    len(x),
                )
            )
            return candidates[0]

    return None


def _infer_specialty_fallback(text: str) -> Optional[str]:
    m = RE_SPECIALTY_INLINE.search(text or "")
    if m:
        return _clean(m.group(1))

    m = RE_SPECIALTY_FALLBACK.search(text or "")
    if not m:
        return None
    return _clean(m.group(1))


def _infer_service_fallback(text: str) -> Optional[str]:
    upper = (text or "").upper()
    if "ENCAMINHAMENTO" in upper and "PSICOLOGIA" in upper:
        return "encaminhamento para psicologia"
    if "PSICOLOGIA" in upper:
        return "psicologia"
    if "ATESTADO" in upper or "AFASTADO" in upper or "INTERNADO" in upper:
        return "atendimento médico"
    return None


def extract_clinical_page_entities(page_text: str) -> Dict[str, Any]:
    text = page_text or ""
    lower = text.lower()

    cids: List[str] = []
    for cid in RE_CID.findall(text):
        if cid.upper() == "S30" and any(ctx in lower for ctx in FALSE_CID_CONTEXT):
            continue
        cids.append(cid)

    medications: List[Dict[str, Any]] = []
    for name, dose in RE_MEDICATION.findall(text):
        name_clean = _clean(name)
        dose_clean = _clean(dose)
        if not name_clean or not dose_clean:
            continue
        if name_clean.lower() in {"numero", "quantidade", "telefone", "endereco"}:
            continue
        medications.append({"name": name_clean, "dose": dose_clean})

    medications = _dedup_dicts(medications, ["name", "dose"])

    posology: List[str] = []
    for m in RE_POSOLOGY.finditer(text):
        p = _clean(m.group(1))
        if p:
            posology.append(p)

    provider_name = None
    m = RE_PROVIDER.search(text)
    if m:
        provider_name = _clean(m.group(1))
    if not provider_name:
        provider_name = _infer_provider_name_fallback(text)

    specialty = None
    m = RE_SPECIALTY.search(text)
    if m:
        specialty = _clean(m.group(1))
    if not specialty:
        specialty = _infer_specialty_fallback(text)

    service = None
    m = RE_SERVICE.search(text)
    if m:
        service = _clean(m.group(1))
    if not service:
        service = _infer_service_fallback(text)

    prescription_numbers = _dedup_strings(RE_PRESCRIPTION_NUMBER.findall(text))

    attendance = None
    m = RE_ATTENDANCE.search(text)
    if m:
        attendance = {
            "date": m.group(1),
            "time": m.group(2),
        }

    return {
        "cids": _dedup_strings(cids),
        "medications": medications,
        "posology": _dedup_strings(posology),
        "provider_name": provider_name,
        "specialty": specialty,
        "service": service,
        "prescription_numbers": prescription_numbers,
        "attendance": attendance,
    }