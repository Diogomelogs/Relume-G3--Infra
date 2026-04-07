from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import re

from PIL import Image
import pytesseract


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


def _clean_text(text: str) -> str:
    text = text.replace("\x0c", " ").replace("\ufeff", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def ocr_image_page(image_path: str, page_number: int) -> OCRPage:
    img = Image.open(image_path).convert("RGB")
    width, height = img.size

    raw_text = pytesseract.image_to_string(img, lang="por+eng", config="--psm 6")
    raw_text = _clean_text(raw_text)

    data = pytesseract.image_to_data(
        img,
        lang="por+eng",
        config="--psm 6",
        output_type=pytesseract.Output.DICT,
    )

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