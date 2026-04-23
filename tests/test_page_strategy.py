from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from relluna.core.document_memory import (
    ArtefatoBruto,
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    Layer2Evidence,
    MediaType,
    OriginType,
)
from relluna.services.page_extraction.page_normalizer import NormalizedPageImage
from relluna.services.page_extraction.page_ocr import OCRPage
from relluna.services.page_extraction.page_strategy import classify_pdf_page_strategies
from relluna.services.pdf_decomposition import decompose_pdf


def _build_pdf_dm(pdf_path: Path) -> DocumentMemory:
    return DocumentMemory(
        version="v0.2.0",
        layer0=Layer0Custodia(
            documentid="page-strategy-doc",
            contentfingerprint="b" * 64,
            ingestiontimestamp=datetime.now(timezone.utc),
            ingestionagent="test",
            original_filename=pdf_path.name,
            mimetype="application/pdf",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="page-strategy-doc",
                    tipo="original",
                    uri=str(pdf_path),
                    nome=pdf_path.name,
                    mimetype="application/pdf",
                    tamanho_bytes=pdf_path.stat().st_size,
                )
            ],
        ),
        layer2=Layer2Evidence(),
    )


def test_classify_pdf_page_strategies_uses_pre_ocr_signals():
    native_pages = [
        {
            "page": 1,
            "text": "Nome do paciente: Maria. Data: 01/01/2024. CRM 12345. " * 3,
            "has_images": False,
            "image_count": 0,
        },
        {
            "page": 2,
            "text": "Parcial 123 com baixa qualidade",
            "has_images": True,
            "image_count": 1,
        },
        {"page": 3, "text": "", "has_images": True, "image_count": 1},
        {"page": 4, "text": "", "has_images": False, "image_count": 0},
    ]

    strategies = classify_pdf_page_strategies(native_pages)

    assert [item["strategy"] for item in strategies] == [
        "native_text",
        "ocr_light",
        "ocr_heavy",
        "image_only",
    ]
    assert all(item["native_text_score"] is not None for item in strategies)


def test_decompose_pdf_routes_ocr_only_to_pages_that_need_it(monkeypatch, tmp_path):
    pdf_path = tmp_path / "heterogeneous.pdf"
    pdf_path.write_bytes(b"stub")
    dm = _build_pdf_dm(pdf_path)

    native_text = "Nome do paciente: Maria. Data: 01/01/2024. CRM 12345. " * 3
    native_pages = [
        {
            "page": 1,
            "text": native_text,
            "source": "native_pdf",
            "has_images": False,
            "image_count": 0,
        },
        {
            "page": 2,
            "text": "",
            "source": "native_pdf",
            "has_images": True,
            "image_count": 1,
        },
        {
            "page": 3,
            "text": "",
            "source": "native_pdf",
            "has_images": False,
            "image_count": 0,
        },
    ]

    def fake_normalize_pdf_pages(*args, **kwargs):
        return [
            NormalizedPageImage(
                page=page,
                image_path=str(pdf_path),
                width=200,
                height=200,
                rotation_applied=0,
                source_pdf_rotation=0,
                orientation_score=0.0,
            )
            for page in [1, 2, 3]
        ]

    def fake_ocr_pages(page_images):
        assert [item["page"] for item in page_images] == [2]
        return [OCRPage(page=2, text="OCR da pagina escaneada", spans=[], width=200, height=200)]

    monkeypatch.setattr(decompose_pdf, "_extract_native_pdf_pages", lambda path: native_pages)
    monkeypatch.setattr(decompose_pdf, "normalize_pdf_pages", fake_normalize_pdf_pages)
    monkeypatch.setattr(decompose_pdf, "ocr_pages", fake_ocr_pages)

    out = decompose_pdf.decompose_pdf_into_subdocuments(dm)

    page_strategy_signal = out.layer2.sinais_documentais["page_strategy_v1"]
    page_strategy = json.loads(page_strategy_signal.valor)
    assert [item["strategy"] for item in page_strategy["pages"]] == [
        "native_text",
        "ocr_heavy",
        "image_only",
    ]

    ocr_pages_signal = out.layer2.sinais_documentais["ocr_pages_v1"]
    ocr_pages = json.loads(ocr_pages_signal.valor)
    assert [(item["page"], item["strategy"], item["status"], item["source"]) for item in ocr_pages] == [
        (1, "native_text", "skipped", "native_pdf"),
        (2, "ocr_heavy", "success", "ocr"),
        (3, "image_only", "skipped", "image_only"),
    ]
