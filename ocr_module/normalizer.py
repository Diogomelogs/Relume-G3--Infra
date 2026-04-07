from __future__ import annotations

import cv2
import numpy as np
import pytesseract
from PIL import Image

from .perspective import auto_perspective_correction


def upscale_to_min_width(img: np.ndarray, min_width: int = 1800) -> np.ndarray:
    h, w = img.shape[:2]
    if w <= 0 or w >= min_width:
        return img
    scale = min_width / float(w)
    return cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def correct_orientation(img: np.ndarray) -> np.ndarray:
    try:
        osd = pytesseract.image_to_osd(Image.fromarray(img), output_type=pytesseract.Output.DICT)
        rotate = int(osd.get('rotate', 0) or 0)
    except Exception:
        rotate = 0
    if rotate == 90:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if rotate == 180:
        return cv2.rotate(img, cv2.ROTATE_180)
    if rotate == 270:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img


def deskew(img: np.ndarray) -> np.ndarray:
    th = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(th > 0))
    if len(coords) < 200:
        return img
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.4 or abs(angle) > 12:
        return img
    h, w = img.shape[:2]
    matrix = cv2.getRotationMatrix2D((w // 2, h // 2), -angle, 1.0)
    return cv2.warpAffine(img, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def normalize(img: np.ndarray, *, fix_perspective: bool = True, min_width: int = 1800, denoise_strength: int = 12) -> np.ndarray:
    if img is None or img.size == 0:
        return img
    work = img.copy()
    if fix_perspective and len(work.shape) == 3:
        work = auto_perspective_correction(work)
    gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY) if len(work.shape) == 3 else work.copy()
    gray = upscale_to_min_width(gray, min_width=min_width)
    gray = correct_orientation(gray)
    gray = cv2.fastNlMeansDenoising(gray, h=denoise_strength)
    gray = deskew(gray)
    return gray
