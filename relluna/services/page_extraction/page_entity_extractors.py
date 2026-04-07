from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

RE_PATIENT = re.compile(
    r"nome\s+paciente[:;\s]+([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇ\s]{5,}?)(?=\s+Nascimento[:;\s]|\s+Sexo[:;\s]|\n|$)",
    re.IGNORECASE,
)
RE_MOTHER = re.compile(
    r"nome\s+da\s+m[aã]e[:;\s]+([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇ\s]{5,}?)(?=\s+\||\s+Nome\s+paciente|\n|$)",
    re.IGNORECASE,
)
RE_BIRTH = re.compile(r"nascimento[:;\s]+(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
RE_SEX = re.compile(r"sexo[:;\s]+([A-Za-zÀ-ÿ]+)", re.IGNORECASE)
RE_RGHC = re.compile(r"\bRGHC[:;\s]+([A-Z0-9]+)\b", re.IGNORECASE)
RE_CPF_FORMATTED = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
RE_CPF_RAW = re.compile(r"(?<![A-Za-z])\d{11}(?![\d-]|[A-Za-z])")
RE_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
RE_CRM = re.compile(r"\bCRM(?:\s*[-:/]?\s*[A-Z]{0,2})?\s*[-:]?\s*(\d{4,8})\b", re.IGNORECASE)
RE_DATE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
RE_PHONE = re.compile(r"(?<!\w)(?:\(?\d{2}\)?\s*)?(?:9?\d{4})-?\d{4}(?!\w)")
RE_AGE = re.compile(r"\bidade[:;\s]+(\d{1,3})\b", re.IGNORECASE)

ORG_PATTERNS = [
    re.compile(r"(Instituto\s+Perdizes\s+do\s+Hospital\s+das\s+Clinicas)", re.IGNORECASE),
    re.compile(r"(Faculdade\s+de\s+Medicina\s+da\s+Universidade\s+de\s+Sao\s+Paulo)", re.IGNORECASE),
    re.compile(r"(AMA/UBS\s+INTEGRADA\s+SITIO\s+DA\s+CASA\s+PINTADA)", re.IGNORECASE),
    re.compile(r"(PREFEITURA\s+DE\s+SAO\s+PAULO)", re.IGNORECASE),
    re.compile(r"(SECRETARIA\s+MUNICIPAL\s+DA\s+SAUDE)", re.IGNORECASE),
    re.compile(r"(PMSP\s*-\s*UNIDADE\s+DE\s+SAUDE)", re.IGNORECASE),
    re.compile(
        r"\b((?:Hospital|Cl[ií]nica|Instituto|Unidade|Centro|Santa\s+Casa)\s+[A-ZÁÀÃÂÉÊÍÓÔÕÚÇa-zà-ÿ0-9][A-ZÁÀÃÂÉÊÍÓÔÕÚÇa-zà-ÿ0-9\s\-]{2,80})",
        re.IGNORECASE,
    ),
]

RE_ADDRESS_LINE = re.compile(
    r"((?:Avenida|Av\.|Rua|R\.|Travessa|Praça)\s+[A-Za-zÀ-ÿ0-9\s]+,\s*\d+.*?)(?=\n|CEP|Telefone|Fone|$)",
    re.IGNORECASE,
)
RE_CEP = re.compile(r"\b\d{5}-?\d{3}\b")
RE_CITY_UF = re.compile(r"\b([A-Za-zÀ-ÿ\s]+)\s*-\s*([A-Z]{2})\b")


def _clean(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = " ".join(value.split()).strip(" |:;,.\t")
    return value or None


def _dedup(values: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for v in values:
        v2 = _clean(v)
        if not v2:
            continue
        key = v2.lower()
        if key not in seen:
            seen.add(key)
            out.append(v2)
    return out


def _validate_cpf(cpf: str) -> bool:
    numbers = re.sub(r"\D", "", cpf)
    if len(numbers) != 11 or numbers == numbers[0] * 11:
        return False

    def calc_digit(n: str) -> int:
        s = sum(int(n[i]) * ((len(n) + 1) - i) for i in range(len(n)))
        d = (s * 10) % 11
        return 0 if d == 10 else d

    return calc_digit(numbers[:9]) == int(numbers[9]) and calc_digit(numbers[:10]) == int(numbers[10])


def _extract_valid_cpfs(text: str) -> List[str]:
    candidates: List[str] = []
    candidates.extend(RE_CPF_FORMATTED.findall(text or ""))
    candidates.extend(RE_CPF_RAW.findall(text or ""))

    out: List[str] = []
    for raw in candidates:
        digits = re.sub(r"\D", "", raw)
        if not _validate_cpf(digits):
            continue
        out.append(digits)

    return _dedup(out)


def _extract_clean_phones(text: str) -> List[str]:
    phones: List[str] = []
    for m in RE_PHONE.finditer(text or ""):
        raw = m.group(0)
        digits = re.sub(r"\D", "", raw)

        if len(digits) in {8, 9}:
            continue
        if len(digits) not in {10, 11}:
            continue
        if len(digits) == 11 and digits[2] != "9":
            continue

        if len(digits) == 11:
            formatted = f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
        else:
            formatted = f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
        phones.append(formatted)

    return _dedup(phones)


def _trim_org_noise(org: str) -> str:
    item = _clean(org) or ""
    if not item:
        return ""

    item = re.sub(r"\s+(?:CRM|CNPJ|Telefone|Fone|CEP)\b.*$", "", item, flags=re.IGNORECASE).strip()
    item = re.sub(r"\s+(?:Rua|R\.|Avenida|Av\.|Travessa|Praça)\b.*$", "", item, flags=re.IGNORECASE).strip()
    item = re.sub(r"\s+\d{1,6}\b.*$", "", item).strip()
    item = item.strip(" -|,.;")
    return item


def _extract_organizations(text: str) -> List[str]:
    orgs: List[str] = []
    for pattern in ORG_PATTERNS:
        orgs.extend(pattern.findall(text or ""))

    cleaned: List[str] = []
    for org in orgs:
        item = _trim_org_noise(org)
        if item:
            cleaned.append(item)

    return _dedup(cleaned)


def _infer_named_person_candidates(text: str) -> List[str]:
    candidates: List[str] = []

    for line in (text or "").splitlines():
        raw = " ".join(line.split()).strip(" |:;,.\t")
        if not raw:
            continue
        if len(raw.split()) < 2 or len(raw.split()) > 6:
            continue
        if re.search(r"\b(?:crm|cpf|cnpj|cid|cep|telefone|fone|rua|avenida|hospital)\b", raw, re.IGNORECASE):
            continue
        if not re.fullmatch(
            r"[A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-Za-zÁÀÃÂÉÊÍÓÔÕÚÇáàãâéêíóôõúç'\-]+(?:\s+[A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-Za-zÁÀÃÂÉÊÍÓÔÕÚÇáàãâéêíóôõúç'\-]+){1,5}",
            raw,
        ):
            continue
        candidates.append(raw)

    return _dedup(candidates)


def _infer_mother_name_fallback(text: str, patient_name: Optional[str]) -> Optional[str]:
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    patient_norm = (patient_name or "").lower().strip()

    for idx, line in enumerate(lines):
        low = line.lower()
        if "mãe" in low or "mae" in low or "filiação" in low or "filiacao" in low:
            if ":" in line:
                _, rhs = line.split(":", 1)
                rhs = _clean(rhs)
                if rhs and rhs.lower() != patient_norm:
                    return rhs

            if idx + 1 < len(lines):
                nxt = _clean(lines[idx + 1])
                if nxt and nxt.lower() != patient_norm:
                    return nxt

    return None


def extract_basic_page_entities(page_text: str) -> Dict[str, Any]:
    text = page_text or ""

    out: Dict[str, Any] = {
        "patient_name": None,
        "mother_name": None,
        "birth_date": None,
        "sex": None,
        "age": None,
        "rghc": None,
        "cpf": [],
        "cnpj": [],
        "crm": [],
        "dates": [],
        "phones": [],
        "organizations": [],
        "address_line": None,
        "cep": None,
        "city": None,
        "uf": None,
        "person_candidates": [],
    }

    m = RE_PATIENT.search(text)
    if m:
        out["patient_name"] = _clean(m.group(1))

    m = RE_MOTHER.search(text)
    if m:
        out["mother_name"] = _clean(m.group(1))

    m = RE_BIRTH.search(text)
    if m:
        out["birth_date"] = m.group(1)

    m = RE_SEX.search(text)
    if m:
        out["sex"] = _clean(m.group(1))

    m = RE_AGE.search(text)
    if m:
        out["age"] = m.group(1)

    m = RE_RGHC.search(text)
    if m:
        out["rghc"] = _clean(m.group(1))

    out["cpf"] = _extract_valid_cpfs(text)
    out["cnpj"] = _dedup(RE_CNPJ.findall(text))
    out["crm"] = _dedup(RE_CRM.findall(text))
    out["dates"] = _dedup(RE_DATE.findall(text))
    out["phones"] = _extract_clean_phones(text)
    out["organizations"] = _extract_organizations(text)

    m = RE_ADDRESS_LINE.search(text)
    if m:
        out["address_line"] = _clean(m.group(1))

    m = RE_CEP.search(text)
    if m:
        cep = re.sub(r"\D", "", m.group(0))
        if len(cep) == 8:
            out["cep"] = f"{cep[:5]}-{cep[5:]}"

    m = RE_CITY_UF.search(text)
    if m:
        out["city"] = _clean(m.group(1))
        out["uf"] = m.group(2)

    out["person_candidates"] = _infer_named_person_candidates(text)

    if not out["mother_name"]:
        out["mother_name"] = _infer_mother_name_fallback(text, out["patient_name"])

    return out