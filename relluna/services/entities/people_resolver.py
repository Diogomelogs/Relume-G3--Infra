from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


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


@dataclass
class PersonResolution:
    name: str
    confidence: float
    reason: str
    evidence_refs: List[Dict[str, Any]] = field(default_factory=list)
    review_state: str = "review_recommended"
    role: Optional[str] = None
    crm: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


class PeopleResolver:
    def resolve(
        self,
        page_evidence_v1: List[Dict[str, Any]],
        layout_spans_v1: Optional[List[Dict[str, Any]]] = None,
        canonical_signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        page_items = page_evidence_v1 or []
        patient = self._pick_role(page_items, "patient_name", "patient")
        patient_identity = self._identity_name(patient.get("name")) if patient else ""
        provider = self._pick_provider(page_items, forbidden_names={patient_identity})
        mother = self._pick_role(
            page_items,
            "mother_name",
            "mother",
            forbidden_names={patient_identity},
        )

        return {
            "patient": patient,
            "provider": provider,
            "mother": mother,
        }

    def _pick_role(
        self,
        page_items: List[Dict[str, Any]],
        role_key: str,
        label: str,
        forbidden_names: Optional[set[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        for page_item in page_items:
            people = page_item.get("people") or {}
            name = self._trim_header_field_noise(people.get(role_key))
            confidence_key = role_key.replace("_name", "_confidence")
            review_key = role_key.replace("_name", "_review_state")
            anchor = self._best_anchor_for_label(page_item, label)
            if not self._looks_like_person_for_role(name, label, anchor, page_item):
                continue
            if self._identity_text(name) in (forbidden_names or set()):
                continue
            confidence = float(people.get(confidence_key) or 0.70)
            evidence = self._evidence_ref(page_item, anchor, label, name)
            score = confidence
            if evidence.get("bbox"):
                score += 0.04
            score -= self._page_rank(page_item) * 0.04
            if label == "patient" and len(str(name).split()) >= 3:
                score += 0.06

            candidates.append(
                {
                    "name": name,
                    "confidence": round(confidence, 3),
                    "reason": f"{label}_anchor_candidate",
                    "review_state": people.get(review_key) or "review_recommended",
                    "evidence_refs": [evidence],
                    "_score": score,
                }
            )

        return self._best_candidate(candidates)

    def _pick_provider(
        self,
        page_items: List[Dict[str, Any]],
        forbidden_names: Optional[set[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        for page_item in page_items:
            people = page_item.get("people") or {}
            name, role = self._extract_provider_name(people.get("provider_name"))
            if not name or self._identity_text(name) in (forbidden_names or set()):
                continue

            anchor = self._best_anchor_for_label(page_item, "provider")
            crm = self._normalize_crm(
                (page_item.get("administrative_entities") or {}).get("crm") or [],
                page_item.get("page_text") or "",
            )
            confidence = float(people.get("provider_confidence") or 0.70)
            evidence = self._evidence_ref(page_item, anchor, "provider", name)
            score = confidence + (0.08 if crm else 0.0)
            if evidence.get("bbox"):
                score += 0.04
            score -= self._page_rank(page_item) * 0.03

            candidates.append(
                {
                    "name": name,
                    "role": role,
                    "crm": crm,
                    "confidence": round(confidence, 3),
                    "reason": "provider_anchor_candidate",
                    "review_state": people.get("provider_review_state") or "review_recommended",
                    "evidence_refs": [evidence],
                    "_score": score,
                }
            )

        return self._best_candidate(candidates)

    def _best_candidate(self, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not candidates:
            return None
        candidates.sort(
            key=lambda c: (
                -float(c["_score"]),
                0 if c["evidence_refs"][0].get("bbox") else 1,
                c["evidence_refs"][0].get("page") or 999,
            )
        )
        best = dict(candidates[0])
        best.pop("_score", None)
        return PersonResolution(**best).to_dict()

    def _best_anchor_for_label(self, page_item: Dict[str, Any], label: str) -> Optional[Dict[str, Any]]:
        candidates = [anchor for anchor in page_item.get("anchors") or [] if anchor.get("label") == label]
        if not candidates:
            return None
        candidates.sort(
            key=lambda anchor: (
                0 if anchor.get("bbox") else 1,
                -(float(anchor.get("confidence") or 0.0)),
            )
        )
        return candidates[0]

    def _evidence_ref(
        self,
        page_item: Dict[str, Any],
        anchor: Optional[Dict[str, Any]],
        label: str,
        name: str,
    ) -> Dict[str, Any]:
        return {
            "page": page_item.get("page"),
            "bbox": anchor.get("bbox") if anchor else None,
            "snippet": anchor.get("snippet") if anchor else f"{label}: {name}",
            "source_path": anchor.get("source_path") if anchor else "layer2.sinais_documentais.page_evidence_v1",
            "provenance_status": "exact" if anchor and anchor.get("bbox") else "text_fallback",
        }

    def _looks_like_person_for_role(
        self,
        value: Optional[str],
        label: str,
        anchor: Optional[Dict[str, Any]] = None,
        page_item: Optional[Dict[str, Any]] = None,
    ) -> bool:
        value = self._trim_header_field_noise(value)
        if not value or self._contains_implausible_text(value):
            return False
        tokens = value.split()
        if len(tokens) < 2 or len(tokens) > 8:
            return False
        if (
            label == "patient"
            and len(tokens) < 3
            and not (
                self._has_strong_patient_anchor(anchor)
                or self._has_strong_patient_page_context(page_item, value)
            )
        ):
            return False
        if re.search(r"\d", value):
            return False
        if value.lower() in {"são paulo", "sao paulo"}:
            return False
        return True

    def _has_strong_patient_anchor(self, anchor: Optional[Dict[str, Any]]) -> bool:
        if not anchor:
            return False
        snippet = self._norm_text(anchor.get("snippet"))
        if "nome da mãe" in snippet or "nome da mae" in snippet:
            return False
        if not anchor.get("bbox"):
            return False
        return bool(
            re.search(
                r"\b(?:paciente|nome\s+paciente|nome)\s*:",
                snippet,
                re.IGNORECASE,
            )
        )

    def _has_strong_patient_page_context(
        self,
        page_item: Optional[Dict[str, Any]],
        value: Optional[str],
    ) -> bool:
        page_text = str((page_item or {}).get("page_text") or "")
        name = self._trim_header_field_noise(value)
        if not page_text or not name:
            return False

        return bool(
            re.search(
                rf"(?im)\b(?:paciente|nome\s+paciente|nome(?!\s+da\s+m[ãa]e))\s*[:\-]?\s*{re.escape(name)}\b",
                page_text,
            )
        )

    def _contains_implausible_text(self, value: str) -> bool:
        low = value.lower()
        if any(item in low for item in _HARD_NON_PERSON):
            return True
        return bool(
            re.search(
                r"\b(?:medicamentos?|subst[âa]ncias?|emitente|fornecedor|comprador|identifica[cç][aã]o|estado|normal|servi[cç]o|especialidade)\b",
                low,
            )
        )

    def _extract_provider_name(self, raw: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        raw = self._trim_header_field_noise(raw)
        if not raw or not self._looks_like_person_for_role(raw, "provider"):
            return None, None
        tokens = raw.split()
        if len(tokens) >= 3:
            for idx in range(len(tokens) - 1, 0, -1):
                tail = " ".join(tokens[idx:])
                if any(word.lower() in tail.lower() for word in ["médico", "medico", "clínico", "clinico"]):
                    head = " ".join(tokens[:idx]).strip()
                    if self._looks_like_person_for_role(head, "provider"):
                        return head, tail
        return raw, None

    def _normalize_crm(self, raw_values: List[str], text: str) -> Optional[Dict[str, Any]]:
        candidates = list(raw_values or [])
        match = re.search(r"\bCRM\s*[-:]?\s*([0-9]{4,8})\s*([A-Z]{2})?\b", text or "", re.IGNORECASE)
        if match:
            candidates.append(f"CRM {match.group(1)}" + (f" {match.group(2)}" if match.group(2) else ""))
        for raw in candidates:
            match2 = re.search(r"\bCRM\s*[-:]?\s*([0-9]{4,8})\s*([A-Z]{2})?\b", raw or "", re.IGNORECASE)
            if match2:
                number = match2.group(1)
                uf = match2.group(2)
                return {"number": number, "uf": uf, "display": f"CRM {number}" + (f" {uf}" if uf else "")}
        return None

    def _trim_header_field_noise(self, text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        cleaned = re.sub(r"\s+", " ", str(text)).strip()
        if not cleaned:
            return None
        for token in _HEADER_BREAK_TOKENS:
            cleaned = re.sub(rf"(?i)\s+\b{re.escape(token)}\b.*$", "", cleaned).strip()
        cleaned = cleaned.strip(" -:|,.;")
        return cleaned or None

    def _page_rank(self, page_item: Dict[str, Any]) -> int:
        taxonomy = ((page_item.get("page_taxonomy") or {}).get("value") or "").lower()
        if taxonomy in {"atestado_medico", "parecer_medico", "laudo_medico"}:
            return 0
        if taxonomy == "documento_composto":
            return 1
        if taxonomy == "documento_medico":
            return 2
        if taxonomy == "formulario_administrativo":
            return 4
        return 3

    def _norm_name(self, person: Optional[Dict[str, Any]]) -> str:
        if not person:
            return ""
        return self._norm_text(person.get("name"))

    def _identity_name(self, value: Optional[str]) -> str:
        return self._identity_text(value)

    def _norm_text(self, value: Optional[str]) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip()).lower()

    def _identity_text(self, value: Optional[str]) -> str:
        normalized = self._norm_text(value)
        normalized = re.sub(r"(?i)^(?:dr|dra|sr|sra)\.?\s+", "", normalized)
        normalized = re.sub(r"[^a-zà-ÿ\s]", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()
