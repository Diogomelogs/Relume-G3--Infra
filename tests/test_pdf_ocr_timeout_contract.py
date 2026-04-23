from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfWriter

from relluna.core.document_memory import (
    ArtefatoBruto,
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    MediaType,
    OriginType,
)
from relluna.services.ingestion import api
from relluna.services.page_extraction import page_normalizer, page_ocr
from relluna.services.page_extraction.page_normalizer import NormalizedPageImage
from relluna.services.page_extraction.page_ocr import OCRPage
from relluna.services.pdf_decomposition import decompose_pdf


def _build_pdf_dm(pdf_path: Path) -> DocumentMemory:
    return DocumentMemory(
        version="v0.2.0",
        layer0=Layer0Custodia(
            documentid="ocr-timeout-doc",
            contentfingerprint="a" * 64,
            ingestiontimestamp=datetime.now(timezone.utc),
            ingestionagent="test",
            original_filename=pdf_path.name,
            mimetype="application/pdf",
            processingevents=[],
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="ocr-timeout-doc",
                    tipo="original",
                    uri=str(pdf_path),
                    nome=pdf_path.name,
                    mimetype="application/pdf",
                    tamanho_bytes=pdf_path.stat().st_size,
                )
            ],
        ),
    )


def _blank_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with path.open("wb") as f:
        writer.write(f)


def test_orientation_ocr_timeout_degrades_with_structured_warning(monkeypatch):
    def timeout(*args, **kwargs):
        raise RuntimeError("Tesseract process timeout")

    monkeypatch.setattr(page_normalizer.pytesseract, "image_to_string", timeout)

    image = Image.new("RGB", (100, 100), "white")
    score, warning = page_normalizer._ocr_orientation_score(
        image,
        lang="por+eng",
        angle=0,
    )

    assert score == -1.0
    assert warning == {
        "code": "ocr_orientation_timeout",
        "severity": "warning",
        "message": "OCR de orientação excedeu o timeout; seguindo sem rotação automática.",
        "engine": "tesseract",
        "lang": "por+eng",
        "angle": 0,
        "timeout_seconds": page_normalizer.ORIENTATION_OCR_TIMEOUT_SECONDS,
    }


def test_pick_best_orientation_tries_landscape_rotations(monkeypatch):
    def fake_score(_img, lang="por", *, angle=0):
        scores = {0: 5.0, 90: 20.0, 270: 10.0}
        return scores[angle], None

    monkeypatch.setattr(page_normalizer, "_ocr_orientation_score", fake_score)

    image = Image.new("RGB", (300, 100), "white")
    best_img, best_rotation, best_score, warnings = page_normalizer._pick_best_orientation(
        image,
        lang="por+eng",
    )

    assert best_rotation == 90
    assert best_score == 20.0
    assert warnings == []
    assert best_img.size == (100, 300)


def test_main_ocr_timeout_returns_degraded_page(monkeypatch, tmp_path):
    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == page_ocr.OCR_PAGE_TIMEOUT_SECONDS
        raise RuntimeError("Tesseract process timeout")

    image_path = tmp_path / "page.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    monkeypatch.setattr(page_ocr.pytesseract, "image_to_string", timeout)

    result = page_ocr.ocr_image_page(str(image_path), page_number=3)

    assert result.page == 3
    assert result.text == ""
    assert result.spans == []
    assert result.warnings == [
        {
            "code": "ocr_page_timeout",
            "severity": "warning",
            "message": "OCR principal excedeu o timeout; página mantida em modo degradado.",
            "engine": "tesseract",
            "page": 3,
            "step": "image_to_string",
            "timeout_seconds": page_ocr.OCR_PAGE_TIMEOUT_SECONDS,
            "cause_message": "Tesseract process timeout",
        }
    ]


@pytest.mark.asyncio
async def test_extract_records_ocr_orientation_warning_processing_event(monkeypatch, tmp_path):
    pdf_path = tmp_path / "scanned.pdf"
    _blank_pdf(pdf_path)
    dm = _build_pdf_dm(pdf_path)
    store = {dm.layer0.documentid: dm}

    async def fake_get(documentid: str):
        current = store.get(documentid)
        if isinstance(current, DocumentMemory):
            return current.model_dump(mode="json", exclude_none=False)
        return current

    async def fake_save(next_dm: DocumentMemory):
        store[next_dm.layer0.documentid] = next_dm.model_copy(deep=True)

    def fake_normalize_pdf_pages(*args, **kwargs):
        return [
            NormalizedPageImage(
                page=1,
                image_path=str(pdf_path),
                width=200,
                height=200,
                rotation_applied=0,
                source_pdf_rotation=0,
                orientation_score=-1.0,
                warnings=[
                    {
                        "code": "ocr_orientation_timeout",
                        "severity": "warning",
                        "message": "OCR de orientação excedeu o timeout; seguindo sem rotação automática.",
                        "engine": "tesseract",
                        "lang": "por+eng",
                        "angle": 0,
                        "timeout_seconds": 5,
                        "page": 1,
                    }
                ],
            )
        ]

    def fake_ocr_pages(page_images):
        return [OCRPage(page=1, text="Atestado 01/01/2024", spans=[], width=200, height=200)]

    monkeypatch.setattr(api.mongo_store, "get", fake_get)
    monkeypatch.setattr(api.mongo_store, "save", fake_save)
    monkeypatch.setattr(decompose_pdf, "normalize_pdf_pages", fake_normalize_pdf_pages)
    monkeypatch.setattr(decompose_pdf, "ocr_pages", fake_ocr_pages)

    result = await api.extract(dm.layer0.documentid)

    assert result is not None
    saved_dm = store[dm.layer0.documentid]
    warning_events = [
        event
        for event in saved_dm.layer0.processingevents
        if event.status == "warning" and event.detalhes.get("code") == "ocr_orientation_timeout"
    ]
    assert warning_events

    warning_signal = saved_dm.layer2.sinais_documentais["ocr_warnings_v1"]
    warnings = json.loads(warning_signal.valor)
    assert warnings[0]["code"] == "ocr_orientation_timeout"
    assert warnings[0]["page"] == 1


@pytest.mark.asyncio
async def test_extract_degrades_on_main_ocr_timeout(monkeypatch, tmp_path):
    pdf_path = tmp_path / "scanned-timeout.pdf"
    _blank_pdf(pdf_path)
    dm = _build_pdf_dm(pdf_path)
    store = {dm.layer0.documentid: dm}

    async def fake_get(documentid: str):
        current = store.get(documentid)
        if isinstance(current, DocumentMemory):
            return current.model_dump(mode="json", exclude_none=False)
        return current

    async def fake_save(next_dm: DocumentMemory):
        store[next_dm.layer0.documentid] = next_dm.model_copy(deep=True)

    def fake_normalize_pdf_pages(*args, **kwargs):
        return [
            NormalizedPageImage(
                page=1,
                image_path=str(pdf_path),
                width=200,
                height=200,
                rotation_applied=0,
                source_pdf_rotation=0,
                orientation_score=0.0,
                warnings=[],
            )
        ]

    def timeout_ocr_pages(page_images):
        raise RuntimeError("Tesseract process timeout while OCRing page 1")

    monkeypatch.setattr(api.mongo_store, "get", fake_get)
    monkeypatch.setattr(api.mongo_store, "save", fake_save)
    monkeypatch.setattr(
        decompose_pdf,
        "_extract_native_pdf_pages",
        lambda path: [
            {
                "page": 1,
                "text": "",
                "source": "native_pdf",
                "has_images": True,
                "image_count": 1,
            }
        ],
    )
    monkeypatch.setattr(decompose_pdf, "normalize_pdf_pages", fake_normalize_pdf_pages)
    monkeypatch.setattr(decompose_pdf, "ocr_pages", timeout_ocr_pages)

    result = await api.extract(dm.layer0.documentid)
    assert result is not None

    saved_dm = store[dm.layer0.documentid]
    warning_events = [
        event
        for event in saved_dm.layer0.processingevents
        if event.status == "warning" and event.detalhes.get("code") == "ocr_page_timeout"
    ]
    assert warning_events
    assert warning_events[0].detalhes["page"] == 1
    assert warning_events[0].detalhes["cause_message"] == "Tesseract process timeout while OCRing page 1"

    warning_signal = saved_dm.layer2.sinais_documentais["ocr_warnings_v1"]
    assert "null" not in warning_signal.valor
    warnings = json.loads(warning_signal.valor)
    assert warnings == [
        {
            "code": "ocr_page_timeout",
            "severity": "warning",
            "message": "OCR principal excedeu o timeout; página mantida em modo degradado.",
            "engine": "tesseract",
            "page": 1,
            "step": "ocr_pages",
            "timeout_seconds": decompose_pdf.OCR_PAGE_TIMEOUT_SECONDS,
            "cause_message": "Tesseract process timeout while OCRing page 1",
        }
    ]

    ocr_pages_signal = saved_dm.layer2.sinais_documentais["ocr_pages_v1"]
    ocr_pages = json.loads(ocr_pages_signal.valor)
    assert ocr_pages[0]["status"] == "degraded"
    assert ocr_pages[0]["text"] == ""
