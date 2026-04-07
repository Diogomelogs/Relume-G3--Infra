import sys
import cv2
import numpy as np
import pytesseract
from PIL import Image
import fitz
from pathlib import Path

def run_tesseract(frame, config) -> tuple[str, float]:
    pil = Image.fromarray(frame)
    data = pytesseract.image_to_data(pil, lang="por", config=config, output_type=pytesseract.Output.DICT)
    
    texts = []
    confs = []
    for text, conf in zip(data.get("text", []), data.get("conf", [])):
        t = (text or "").strip()
        try:
            c = float(conf)
        except Exception:
            c = -1.0
        if t and len(t) > 1:
            texts.append(t)
        if c >= 0:
            confs.append(c)

    text = " ".join(texts).strip()
    avg_conf = sum(confs) / len(confs) if confs else 0.0
    return text, avg_conf

def four_point_transform(image, pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    
    (tl, tr, br, bl) = rect
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxW = max(int(widthA), int(widthB))
    maxH = max(int(heightA), int(heightB))
    
    dst = np.array([
        [0, 0],
        [maxW - 1, 0],
        [maxW - 1, maxH - 1],
        [0, maxH - 1]
    ], dtype="float32")
    
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (maxW, maxH))

def perspective_fix(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 75, 200)
    
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            pts = approx.reshape(4, 2).astype("float32")
            return four_point_transform(img, pts)
    return img

def deskew_agressivo(gray):
    inv = cv2.bitwise_not(gray)
    coords = np.column_stack(np.where(inv > 0))
    if len(coords) < 100:
        return gray
    
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5:
        return gray
        
    (h, w) = gray.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), -angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

def otsu_morph(gray):
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
    return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

def extract_rg(path: str | Path):
    path = Path(path)
    
    if path.suffix.lower() == '.pdf':
        doc = fitz.open(path)
        page = doc[0]
        pix = page.get_pixmap(dpi=600)  # Força DPI alto
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        doc.close()
    else:
        img = cv2.imread(str(path))
    
    print(f"\n📂 Arquivo: {path.name}")
    print(f"📐 Resolução inicial: {img.shape[1]}x{img.shape[0]}")
    
    # Processamento
    img = perspective_fix(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = deskew_agressivo(gray)
    
    # Variants
    binary1 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 15)
    binary2 = otsu_morph(gray)
    
    kernel_sharp = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharp = cv2.filter2D(binary1, -1, kernel_sharp)
    
    # Roda OCR (whitelist focada em RG/Identidade)
    whitelist = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZÀÁÂÃÄÅÇÉÊËÍÎÏÓÔÕÖÚÛÜ -/."
    config = f"--oem 3 --psm 6 -c tessedit_char_whitelist='{whitelist}'"
    
    results = {}
    for name, frame in [("adaptive", binary1), ("otsu", binary2), ("sharp", sharp)]:
        text, conf = run_tesseract(frame, config)
        results[name] = {"text": text, "conf": conf}
    
    # Pega o que retornou mais caracteres alfanuméricos
    best = max(results.items(), key=lambda x: (len(x[1]["text"].replace(" ", "")), x[1]["conf"]))
    
    print(f"\n🏆 MELHOR VARIANT: {best[0].upper()} | Conf: {best[1]['conf']:.1f}%")
    print("-" * 50)
    print(best[1]['text'])
    print("-" * 50)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        extract_rg(sys.argv[1])
    else:
        print("Uso: python rg_extractor.py <caminho_do_arquivo>")
