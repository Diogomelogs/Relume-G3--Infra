from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any
import re

from PIL import Image
import pytesseract

OCR_PAGE_TIMEOUT_SECONDS = 8


@dataclass
class OCRSpan:
    page: int
    text: str
    bbox: list[float]


@dataclass
class OCRPage:
    page: int
    text: str
    spans: List[OCRSpan]
    width: int
    height: int
    warnings: List[Dict[str, Any]] = field(default_factory=list)


def _clean_text(text: str) -> str:
    text = text.replace("\x0c", " ").replace("\ufeff", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_tesseract_timeout(exc: RuntimeError) -> bool:
    return "timeout" in str(exc).lower()


def _ocr_timeout_warning(page_number: int, step: str, exc: RuntimeError) -> Dict[str, Any]:
    return {
        "code": "ocr_page_timeout",
        "severity": "warning",
        "message": "OCR principal excedeu o timeout; página mantida em modo degradado.",
        "engine": "tesseract",
        "page": page_number,
        "step": step,
        "timeout_seconds": OCR_PAGE_TIMEOUT_SECONDS,
        "cause_message": str(exc) or exc.__class__.__name__,
    }


def ocr_image_page(image_path: str, page_number: int) -> OCRPage:
    img = Image.open(image_path).convert("RGB")
    width, height = img.size

    try:
        raw_text = pytesseract.image_to_string(
            img,
            lang="por+eng",
            config="--psm 6",
            timeout=OCR_PAGE_TIMEOUT_SECONDS,
        )
    except RuntimeError as exc:
        if _is_tesseract_timeout(exc):
            return OCRPage(
                page=page_number,
                text="",
                spans=[],
                width=width,
                height=height,
                warnings=[_ocr_timeout_warning(page_number, "image_to_string", exc)],
            )
        raise
    raw_text = _clean_text(raw_text)

    try:
        data = pytesseract.image_to_data(
            img,
            lang="por+eng",
            config="--psm 6",
            output_type=pytesseract.Output.DICT,
            timeout=OCR_PAGE_TIMEOUT_SECONDS,
        )
    except RuntimeError as exc:
        if _is_tesseract_timeout(exc):
            return OCRPage(
                page=page_number,
                text=raw_text,
                spans=[],
                width=width,
                height=height,
                warnings=[_ocr_timeout_warning(page_number, "image_to_data", exc)],
            )
        raise

    spans: List[OCRSpan] = []
    n = len(data["text"])
    for i in range(n):
        text = (data["text"][i] or "").strip()
        conf = data["conf"][i]
        if not text:
            continue
        try:
            conf_val = float(conf)
        except Exception:
            conf_val = -1
        if conf_val < 20:
            continue

        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        spans.append(
            OCRSpan(
                page=page_number,
                text=text,
                bbox=[float(x), float(y), float(x + w), float(y + h)],
            )
        )

    return OCRPage(
        page=page_number,
        text=raw_text,
        spans=spans,
        width=width,
        height=height,
    )


def ocr_pages(page_images: List[Dict[str, Any]]) -> List[OCRPage]:
    pages: List[OCRPage] = []
    for item in page_images:
        pages.append(ocr_image_page(item["image_path"], item["page"]))
    return pages
