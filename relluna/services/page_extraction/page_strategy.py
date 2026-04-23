from __future__ import annotations

from typing import Any, Dict, List, Literal

PageStrategy = Literal["native_text", "ocr_light", "ocr_heavy", "image_only"]


def _safe_text(value: Any) -> str:
    return (value or "").strip()


def _text_quality_score(text: str) -> float:
    text = _safe_text(text)
    if not text:
        return 0.0

    alpha_chars = sum(1 for c in text if c.isalpha())
    digit_chars = sum(1 for c in text if c.isdigit())
    spaces = sum(1 for c in text if c.isspace())
    weird_chars = len(text) - alpha_chars - digit_chars - spaces

    score = 0.0
    score += min(len(text) / 300.0, 4.0)
    score += min(alpha_chars / max(len(text), 1), 1.0) * 3.0
    score += min(digit_chars / max(len(text), 1), 1.0) * 0.5
    score -= min(weird_chars / max(len(text), 1), 1.0) * 2.0

    lowered = text.lower()
    for hint in [
        "nome",
        "data",
        "cpf",
        "cnpj",
        "crm",
        "paciente",
        "hospital",
        "beneficio",
        "benefício",
        "receituario",
        "receituário",
        "assinatura",
    ]:
        if hint in lowered:
            score += 0.5

    return score


def classify_pdf_page_strategy(page: Dict[str, Any]) -> Dict[str, Any]:
    text = _safe_text(page.get("text"))
    text_len = len(text)
    score = _text_quality_score(text)
    image_count = int(page.get("image_count") or 0)
    has_images = bool(page.get("has_images")) or image_count > 0

    if text_len >= 80 and score >= 2.5:
        strategy: PageStrategy = "native_text"
        reason = "native_text_quality_sufficient"
        confidence = 0.95
    elif text_len == 0 and not has_images:
        strategy = "image_only"
        reason = "no_native_text_or_pdf_image_xobject"
        confidence = 0.70
    elif text_len >= 20 and score >= 1.0 and not has_images:
        strategy = "ocr_light"
        reason = "partial_native_text_without_image_layer"
        confidence = 0.80
    elif text_len >= 20 and score >= 1.0:
        strategy = "ocr_light"
        reason = "partial_native_text_with_image_layer"
        confidence = 0.75
    else:
        strategy = "ocr_heavy"
        reason = "native_text_missing_or_low_quality"
        confidence = 0.85 if has_images else 0.65

    return {
        "page": int(page.get("page") or 0),
        "strategy": strategy,
        "reason": reason,
        "confidence": confidence,
        "native_text_chars": text_len,
        "native_text_score": round(score, 3),
        "has_images": has_images,
        "image_count": image_count,
    }


def classify_pdf_page_strategies(native_pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [classify_pdf_page_strategy(page) for page in native_pages]
