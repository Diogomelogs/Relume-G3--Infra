from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import tempfile
import re

import fitz  # PyMuPDF
from PIL import Image, ImageOps
import pytesseract


@dataclass
class NormalizedPageImage:
    page: int
    image_path: str
    width: int
    height: int
    rotation_applied: int
    source_pdf_rotation: int
    orientation_score: float


def _render_page_to_pil(doc: fitz.Document, page_index: int, dpi: int = 170) -> Image.Image:
    page = doc.load_page(page_index)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    mode = "RGB" if pix.n < 4 else "RGBA"
    img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
    if mode == "RGBA":
        img = img.convert("RGB")
    return img


def _apply_pdf_rotation(img: Image.Image, pdf_rotation: int) -> Image.Image:
    if pdf_rotation in {90, 180, 270}:
        return img.rotate(-pdf_rotation, expand=True)
    return img


def _ocr_orientation_score(img: Image.Image, lang: str = "por") -> float:
    thumb = img.copy()
    thumb.thumbnail((1400, 1400))
    thumb = ImageOps.grayscale(thumb)
    thumb = ImageOps.autocontrast(thumb)

    try:
        text = pytesseract.image_to_string(thumb, lang=lang, config="--psm 6")
    except Exception:
        return -1.0

    text = text or ""
    alpha_tokens = re.findall(r"[A-Za-zÀ-ÿ]{3,}", text)
    digit_tokens = re.findall(r"\d{2,}", text)
    weird_chars = re.findall(r"[^A-Za-zÀ-ÿ0-9\s\.,;:/\-\(\)]", text)

    score = 0.0
    score += len(alpha_tokens) * 2.0
    score += len(digit_tokens) * 0.7
    score -= len(weird_chars) * 0.5

    lowered = text.lower()
    for hint in [
        "nome", "data", "crm", "cpf", "cnpj", "receituario", "receituário", "paciente",
        "laudo", "exame", "atendimento", "sao paulo", "hospital", "notificação", "notificacao",
        "receita", "controle", "especial", "farmácia", "farmacia", "fornecedor", "comprador"
    ]:
        if hint in lowered:
            score += 4.0

    width, height = thumb.size
    if height > width:
        score += 1.5

    return score


def _pick_best_orientation(img: Image.Image, lang: str = "eng") -> Tuple[Image.Image, int, float]:
    candidates = [0, 90, 180, 270]
    best_img, best_rotation, best_score = img, 0, float("-inf")

    for angle in candidates:
        candidate = img.rotate(angle, expand=True) if angle else img
        score = _ocr_orientation_score(candidate, lang=lang)
        if score > best_score:
            best_score = score
            best_img = candidate
            best_rotation = angle

    return best_img, best_rotation, best_score


def normalize_pdf_pages(
    pdf_path: str,
    out_dir: Optional[str] = None,
    dpi: int = 170,
    lang: str = "por",
) -> List[NormalizedPageImage]:
    pdf_path = str(pdf_path)
    target_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="relluna_pages_"))
    target_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    results: List[NormalizedPageImage] = []

    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        pdf_rotation = int(page.rotation or 0)

        img = _render_page_to_pil(doc, page_index, dpi=dpi)
        img = _apply_pdf_rotation(img, pdf_rotation)
        img = ImageOps.autocontrast(img)

        best_img, extra_rotation, best_score = _pick_best_orientation(img, lang=lang)

        out_path = target_dir / f"page_{page_index + 1:03d}.png"
        best_img.save(out_path, format="PNG")

        results.append(
            NormalizedPageImage(
                page=page_index + 1,
                image_path=str(out_path),
                width=best_img.size[0],
                height=best_img.size[1],
                rotation_applied=extra_rotation,
                source_pdf_rotation=pdf_rotation,
                orientation_score=best_score,
            )
        )

    doc.close()
    return results