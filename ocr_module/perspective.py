from __future__ import annotations

import cv2
import numpy as np


def _order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    rect = _order_points(pts)
    tl, tr, br, bl = rect
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_w = max(int(width_a), int(width_b))
    max_h = max(int(height_a), int(height_b))
    if max_w <= 1 or max_h <= 1:
        return image
    dst = np.array([[0, 0], [max_w - 1, 0], [max_w - 1, max_h - 1], [0, max_h - 1]], dtype="float32")
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (max_w, max_h))


def auto_perspective_correction(img: np.ndarray) -> np.ndarray:
    if img is None or img.size == 0 or len(img.shape) != 3:
        return img
    orig = img.copy()
    h, w = img.shape[:2]
    if min(h, w) < 50:
        return orig
    ratio = h / 600.0
    small = cv2.resize(img, (max(1, int(w / ratio)), 600))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.dilate(edges, kernel, iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
    frame_area = float(small.shape[0] * small.shape[1])
    for contour in contours:
        area = cv2.contourArea(contour)
        if area / frame_area < 0.20:
            continue
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) != 4:
            continue
        pts = approx.reshape(4, 2) * ratio
        return four_point_transform(orig, pts.astype('float32'))
    return orig
