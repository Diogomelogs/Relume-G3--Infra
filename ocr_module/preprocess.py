from __future__ import annotations

import re
from typing import Any

import cv2
import fitz
import numpy as np
import pytesseract
from PIL import Image

from .normalizer import normalize


def read_image(path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f'Falha ao ler imagem: {path}')
    return img


def render_pdf_page(page: fitz.Page, dpi: int = 300) -> np.ndarray:
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def upscale(gray: np.ndarray, min_width: int = 1600) -> np.ndarray:
    h, w = gray.shape[:2]
    if w >= min_width or w == 0:
        return gray
    scale = min_width / float(w)
    return cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def estimate_dark_background(gray: np.ndarray) -> bool:
    h, w = gray.shape[:2]
    border = np.concatenate([gray[: max(1, h // 20), :].ravel(), gray[-max(1, h // 20) :, :].ravel(), gray[:, : max(1, w // 20)].ravel(), gray[:, -max(1, w // 20) :].ravel()])
    return float(np.mean(border)) < 90.0


def invert_if_dark(gray: np.ndarray) -> np.ndarray:
    return cv2.bitwise_not(gray) if estimate_dark_background(gray) else gray


def remove_table_lines(gray: np.ndarray) -> np.ndarray:
    inv = cv2.bitwise_not(gray)
    bw = cv2.adaptiveThreshold(inv, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -2)
    horizontal = bw.copy()
    vertical = bw.copy()
    h_kernel_len = max(15, horizontal.shape[1] // 35)
    v_kernel_len = max(15, vertical.shape[0] // 35)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_len, 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))
    horizontal = cv2.morphologyEx(horizontal, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(vertical, cv2.MORPH_OPEN, vertical_kernel)
    table_mask = cv2.add(horizontal, vertical)
    out = gray.copy()
    out[table_mask == 255] = 255
    return out


def crop_with_padding(img: np.ndarray, x0: int, y0: int, x1: int, y1: int, padding: int = 16) -> np.ndarray:
    h, w = img.shape[:2]
    x0 = max(0, x0 - padding)
    y0 = max(0, y0 - padding)
    x1 = min(w, x1 + padding)
    y1 = min(h, y1 + padding)
    return img[y0:y1, x0:x1].copy()


def crop_non_white_margins(img: np.ndarray, *, threshold: int = 245, padding: int = 18) -> np.ndarray:
    if img is None or img.size == 0:
        return img
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()
    mask = (gray < threshold).astype('uint8') * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    coords = cv2.findNonZero(mask)
    if coords is None:
        return img
    x, y, w, h = cv2.boundingRect(coords)
    return crop_with_padding(img, x, y, x + w, y + h, padding=padding)


def _quick_rotation_score(img: np.ndarray, *, lang: str = 'por+eng') -> float:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()
    gray = upscale(gray, min_width=1000)
    try:
        data = pytesseract.image_to_data(Image.fromarray(gray), lang=lang, config='--oem 3 --psm 6', output_type=pytesseract.Output.DICT, timeout=8)
    except Exception:
        return 0.0
    tokens, confs = [], []
    for text, conf in zip(data.get('text', []), data.get('conf', [])):
        token = (text or '').strip()
        try:
            score = float(conf)
        except Exception:
            score = -1.0
        if token:
            tokens.append(token)
        if score >= 0:
            confs.append(score)
    joined = ' '.join(tokens)
    alpha_words = len(re.findall(r'\b[A-Za-zÀ-ÿ]{3,}\b', joined, flags=re.UNICODE))
    digits = len(re.findall(r'\d', joined))
    avg_conf = (sum(confs) / len(confs)) if confs else 0.0
    return alpha_words * 4.0 + digits * 0.4 + avg_conf * 0.6


def rotate_card_to_upright(img: np.ndarray, *, lang: str = 'por+eng') -> np.ndarray:
    candidates = [img, cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE), cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE), cv2.rotate(img, cv2.ROTATE_180)]
    return max(((candidate, _quick_rotation_score(candidate, lang=lang)) for candidate in candidates), key=lambda item: item[1])[0]


def mask_non_text_regions(img: np.ndarray) -> np.ndarray:
    if img is None or img.size == 0:
        return img
    work = img.copy()
    gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY) if len(work.shape) == 3 else work.copy()
    h, w = gray.shape[:2]
    frame_area = float(h * w)
    th = cv2.threshold(gray, 185, 255, cv2.THRESH_BINARY_INV)[1]
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)))
    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < frame_area * 0.015 or area > frame_area * 0.30:
            continue
        x, y, bw, bh = cv2.boundingRect(contour)
        aspect = max(bw, bh) / max(1, min(bw, bh))
        center_x = x + bw / 2.0
        center_y = y + bh / 2.0
        centerish = (0.15 * w) <= center_x <= (0.85 * w) and (0.10 * h) <= center_y <= (0.90 * h)
        if not centerish or aspect > 2.2:
            continue
        cv2.rectangle(work, (x, y), (x + bw, y + bh), (255, 255, 255), thickness=-1)
    return work


def split_rg_page(img: np.ndarray, *, lang: str = 'por+eng') -> list[dict[str, Any]]:
    if img is None or img.size == 0:
        return []
    band = crop_non_white_margins(img, threshold=245, padding=20)
    if band is None or band.size == 0:
        return []
    h, w = band.shape[:2]
    if h < int(w * 1.20):
        return []
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY) if len(band.shape) == 3 else band.copy()
    mask = (gray < 245).astype('uint8') * 255
    row_coverage = (mask > 0).sum(axis=1)
    max_cov = int(row_coverage.max()) if len(row_coverage) else 0
    if max_cov <= 0:
        return []
    mid = h // 2
    window = max(120, int(h * 0.18))
    start = max(0, mid - window)
    end = min(h, mid + window)
    if end - start < 20:
        return []
    split_idx = int(np.argmin(row_coverage[start:end]) + start)
    split_val = int(row_coverage[split_idx])
    top_h = split_idx
    bot_h = h - split_idx
    valley_ok = split_val <= int(max_cov * 0.68)
    heights_ok = top_h >= int(h * 0.22) and bot_h >= int(h * 0.22)
    if not valley_ok or not heights_ok:
        return []
    pad = max(12, int(h * 0.012))
    top = band[: max(0, split_idx - pad), :]
    bottom = band[min(h, split_idx + pad) :, :]
    cards = []
    for idx, crop in enumerate([top, bottom], start=1):
        crop = crop_non_white_margins(crop, threshold=245, padding=16)
        if crop is None or crop.size == 0 or min(crop.shape[:2]) < 120:
            continue
        oriented = rotate_card_to_upright(crop, lang=lang)
        cards.append({'name': f'card_{idx}', 'image': oriented, 'masked_image': mask_non_text_regions(oriented), 'height': oriented.shape[0], 'width': oriented.shape[1]})
    return cards


def _base_gray(img: np.ndarray, *, min_width: int = 1600) -> np.ndarray:
    return normalize(img, fix_perspective=False, min_width=min_width, denoise_strength=12)


def build_pdf_variants(img: np.ndarray, *, masked_img: np.ndarray | None = None) -> dict[str, np.ndarray]:
    gray = _base_gray(img, min_width=1600)
    variants = {'gray': gray}
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    den = cv2.fastNlMeansDenoising(clahe, h=8)
    otsu = cv2.threshold(den, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    adaptive = cv2.adaptiveThreshold(den, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12)
    sharp_kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    sharp_otsu = cv2.filter2D(otsu, -1, sharp_kernel)
    variants.update({'adaptive': adaptive, 'otsu': otsu, 'sharp_otsu': sharp_otsu, 'no_tables': remove_table_lines(gray)})
    if estimate_dark_background(gray):
        variants['inverted'] = invert_if_dark(gray)
    if masked_img is not None and masked_img.size > 0:
        masked_gray = _base_gray(masked_img, min_width=1600)
        variants['masked_gray'] = masked_gray
        variants['masked_adaptive'] = cv2.adaptiveThreshold(masked_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12)
    return variants


def build_image_variants(img: np.ndarray, *, masked_img: np.ndarray | None = None) -> dict[str, np.ndarray]:
    gray = _base_gray(img, min_width=1800)
    variants = {'gray': gray}
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8)).apply(gray)
    den = cv2.fastNlMeansDenoising(clahe, h=10)
    otsu = cv2.threshold(den, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    adaptive = cv2.adaptiveThreshold(den, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12)
    sharp_kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    sharp_otsu = cv2.filter2D(otsu, -1, sharp_kernel)
    variants.update({'adaptive': adaptive, 'otsu': otsu, 'sharp_otsu': sharp_otsu, 'no_tables': remove_table_lines(gray)})
    if estimate_dark_background(gray):
        variants['inverted'] = invert_if_dark(gray)
    if masked_img is not None and masked_img.size > 0:
        masked_gray = _base_gray(masked_img, min_width=1800)
        variants['masked_gray'] = masked_gray
        variants['masked_adaptive'] = cv2.adaptiveThreshold(masked_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12)
    return variants
