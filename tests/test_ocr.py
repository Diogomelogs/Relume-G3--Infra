from __future__ import annotations

import re
from pathlib import Path

import pytest

from ocr_module import OCRModule

SAMPLES = Path('tests/samples')
SUPPORTED = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.webp'}
FILES = sorted([p for p in SAMPLES.iterdir() if p.suffix.lower() in SUPPORTED], key=lambda p: p.name) if SAMPLES.exists() else []

pytestmark = pytest.mark.xfail(
    reason="OCR real com Tesseract/PDFs de amostra é integração pesada e instável para make test",
    run=False,
    strict=False,
)


def _assert_structured_rg_text(text: str):
    lowered = text.lower()
    assert 'nome' in lowered or 'registro geral' in lowered or 'identidade' in lowered
    assert re.search(r'\b\d{2}/\d{2}/\d{4}\b', text) or 'nascimento' in lowered


@pytest.mark.parametrize('arquivo', FILES, ids=[p.name for p in FILES])
def test_real_files(arquivo: Path):
    ocr = OCRModule(lang='por+eng')
    result = ocr.extract(arquivo)
    ocr.save_artifacts(arquivo, result, out_dir='tests/artifacts')
    print(f"\n{'=' * 72}")
    print(f'Arquivo    : {arquivo.name}')
    print(f'Tipo       : {result.doc_type.value}')
    print(f'Engine     : {result.engine}')
    print(f'Status     : {result.status.value}')
    print(f'Confiança  : {result.confidence}')
    print(f'Páginas    : {result.pages}')
    print(f'Motivos    : {result.reasons}')
    print(f'Métricas   : {result.metrics}')
    print(f'Warnings   : {result.warnings}')
    print(f'Prévia     : {result.text[:500] if result.text else '(sem texto)'}')
    assert result.status.value in {'approved', 'review', 'rejected'}
    assert isinstance(result.reasons, list)
    assert isinstance(result.metrics, dict)
    assert 'document_score' in result.metrics
    if result.status.value == 'approved':
        assert result.text.strip()
        assert result.metrics['score'] >= 72
        assert result.metrics['document_score'] >= 8
    if result.status.value == 'rejected':
        assert result.reasons


@pytest.mark.skipif(not SAMPLES.exists(), reason='Amostras não disponíveis')
def test_whatsapp_noise_should_not_be_approved():
    arquivo = SAMPLES / 'WhatsApp Image 2025-12-28 at 22.32.23 (3).jpeg'
    if not arquivo.exists():
        pytest.skip('Arquivo de WhatsApp não encontrado')
    ocr = OCRModule(lang='por+eng')
    result = ocr.extract(arquivo)
    assert result.status.value != 'approved'


@pytest.mark.skipif(not SAMPLES.exists(), reason='Amostras não disponíveis')
def test_rg_should_keep_structured_fields():
    arquivo = SAMPLES / '20a6d090-c503-44dc-988f-2afa04cb2bc4_RG - DIOGO DE MELO GOMES SILVA.pdf'
    if not arquivo.exists():
        pytest.skip('Arquivo RG não encontrado')
    ocr = OCRModule(lang='por+eng', enable_paddleocr=False)
    result = ocr.extract(arquivo)
    assert result.text.strip()
    assert result.metrics['document_score'] >= 10
    _assert_structured_rg_text(result.text)
