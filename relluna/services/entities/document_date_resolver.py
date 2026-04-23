from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


_BIRTH_DATE_MARKERS = (
    "nascimento",
    "nascto",
    "data de nascimento",
    "idade",
)


@dataclass
class DocumentDateResolution:
    date_iso: str
    literal: str
    confidence: float
    reason: str
    evidence_refs: List[Dict[str, Any]] = field(default_factory=list)
    review_state: str = "review_recommended"
    provenance_status: str = "text_fallback"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DocumentDateResolver:
    def resolve(
        self,
        page_evidence_v1: List[Dict[str, Any]],
        layout_spans_v1: Optional[List[Dict[str, Any]]] = None,
        canonical_signals: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        candidates = self._candidates(page_evidence_v1 or [])
        candidates = [candidate for candidate in candidates if candidate["_score"] > 0.20]
        if not candidates:
            return None

        candidates.sort(
            key=lambda c: (
                -(1.0 if c["evidence_refs"][0].get("bbox") else 0.0),
                -float(c["_score"]),
                c["evidence_refs"][0].get("page") or 999,
            )
        )
        best = dict(candidates[0])
        best.pop("_score", None)
        return DocumentDateResolution(**best).to_dict()

    def _candidates(self, page_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        for page_item in page_items:
            page_text = str(page_item.get("page_text") or "")
            for item in page_item.get("date_candidates") or []:
                literal = item.get("literal")
                date_iso = item.get("date_iso")
                if not literal or not date_iso:
                    continue

                anchor = self._date_anchor(page_item, literal, date_iso)
                snippet = anchor.get("snippet") if anchor else literal
                if self._looks_like_birth_date_context(snippet, page_text, literal):
                    continue

                score = 0.70
                if anchor and anchor.get("bbox"):
                    score += 0.20
                if self._page_rank(page_item) <= 1:
                    score += 0.05
                score += self._date_context_penalty(snippet, page_text, literal)

                evidence = {
                    "page": page_item.get("page"),
                    "bbox": anchor.get("bbox") if anchor else None,
                    "snippet": snippet,
                    "source_path": anchor.get("source_path") if anchor else "layer2.texto_ocr_literal.valor",
                    "provenance_status": "exact" if anchor and anchor.get("bbox") else "text_fallback",
                }
                confidence = 0.97 if anchor and anchor.get("bbox") else round(max(score, 0.05), 3)
                candidates.append(
                    {
                        "date_iso": date_iso,
                        "literal": literal,
                        "confidence": confidence,
                        "reason": "date_anchor_not_birth_context"
                        if anchor
                        else "date_candidate_not_birth_context",
                        "evidence_refs": [evidence],
                        "review_state": "auto_confirmed" if anchor and anchor.get("bbox") else "review_recommended",
                        "provenance_status": evidence["provenance_status"],
                        "_score": score,
                    }
                )
        return candidates

    def _date_anchor(self, page_item: Dict[str, Any], literal: str, date_iso: str) -> Optional[Dict[str, Any]]:
        for anchor in page_item.get("anchors") or []:
            if anchor.get("label") == "date" and (
                anchor.get("value") == date_iso or anchor.get("snippet") == literal
            ):
                return anchor
        return None

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

    def _date_context_penalty(self, snippet: str, page_text: str, literal: str) -> float:
        snippet_low = str(snippet or "").lower()
        text_low = str(page_text or "").lower()
        literal_low = str(literal or "").lower()
        penalty = 0.0

        if any(marker in snippet_low for marker in _BIRTH_DATE_MARKERS):
            penalty -= 1.0

        idx = text_low.find(literal_low)
        if idx >= 0:
            line = self._line_window(text_low, idx)
            if any(marker in line for marker in _BIRTH_DATE_MARKERS):
                penalty -= 1.2
            if any(marker in line for marker in ("data:", "emissão", "emissao", "assinatura")):
                penalty += 0.45

        return penalty

    def _looks_like_birth_date_context(self, snippet: str, page_text: str, literal: str) -> bool:
        snippet_low = str(snippet or "").lower()
        text_low = str(page_text or "").lower()
        literal_low = str(literal or "").lower()

        if any(marker in snippet_low for marker in _BIRTH_DATE_MARKERS):
            return True

        idx = text_low.find(literal_low)
        if idx < 0:
            return False
        return any(marker in self._line_window(text_low, idx) for marker in _BIRTH_DATE_MARKERS)

    def _line_window(self, text: str, idx: int) -> str:
        line_start = text.rfind("\n", 0, idx) + 1
        line_end = text.find("\n", idx)
        if line_end < 0:
            line_end = len(text)
        return text[line_start:line_end]
