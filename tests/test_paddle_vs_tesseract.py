from __future__ import annotations

from pathlib import Path

import fitz
import numpy as np
import pytest
from PIL import Image

from ocr_module import OCRModule

SAMPLES = Path('tests/samples')

pytestmark = pytest.mark.xfail(
    reason="comparação Paddle/Tesseract é integração OCR pesada e dependente do ambiente",
    run=False,
    strict=False,
)


def _read_pdf_page_as_np(path: Path, page_idx: int = 0) -> np.ndarray:
    doc = fitz.open(path)
    page = doc[page_idx]
    pix = page.get_pixmap(dpi=300)
    img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
    img_np = np.array(img)
    doc.close()
    return img_np


@pytest.mark.skipif(not SAMPLES.exists(), reason='Amostras não disponíveis')
def test_rg_paddle_vs_tesseract_smoke():
    arquivo = SAMPLES / '20a6d090-c503-44dc-988f-2afa04cb2bc4_RG - DIOGO DE MELO GOMES SILVA.pdf'
    if not arquivo.exists():
        pytest.skip('Arquivo RG não encontrado')
    tesseract_ocr = OCRModule(lang='por+eng', enable_paddleocr=False)
    tess_result = tesseract_ocr.extract(arquivo)
    print('🔵 TESSERACT')
    print(f'Status: {tess_result.status.value} | Conf: {tess_result.confidence}')
    print(f"Score: {tess_result.metrics.get('score', 'N/A')}")
    print(f"Document score: {tess_result.metrics.get('document_score', 'N/A')}")
    print(f"Text: {tess_result.text[:400] if tess_result.text else '(vazio)'}")
    try:
        from paddleocr import PaddleOCR
    except Exception:
        pytest.skip('PaddleOCR não disponível no ambiente')
    img_np = _read_pdf_page_as_np(arquivo)
    ocr = PaddleOCR(use_textline_orientation=True, lang='pt')
    result = ocr.ocr(img_np)
    paddle_text = ''
    paddle_confs = []
    if result and result[0]:
        for line in result[0]:
            txt = line[1][0]
            conf = line[1][1] * 100
            paddle_text += txt + '\n'
            paddle_confs.append(conf)
    avg_conf = sum(paddle_confs) / len(paddle_confs) if paddle_confs else 0
    print('\n🟢 PADDLEOCR')
    print(f'Linhas detectadas: {len(paddle_confs)}')
    print(f'Conf média: {avg_conf:.1f}%')
    print(f'Text:\n{paddle_text}')
    assert tess_result.text is not None


@pytest.mark.skipif(not SAMPLES.exists(), reason='Amostras não disponíveis')
def test_pipeline_with_paddle_fallback_smoke():
    arquivo = SAMPLES / 'WhatsApp Image 2025-12-28 at 22.32.23 (3).jpeg'
    if not arquivo.exists():
        pytest.skip('Arquivo de WhatsApp não encontrado')
    ocr = OCRModule(lang='por+eng', enable_paddleocr=True)
    result = ocr.extract(arquivo)
    assert result.status.value in {'approved', 'review', 'rejected'}
    assert isinstance(result.candidates, list)
