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
from relluna.core.document_memory.layer1 import ArtefatoTipo
from relluna.services.page_extraction.page_normalizer import NormalizedPageImage
from relluna.services.page_extraction.page_ocr import OCRPage
from relluna.services.page_extraction.page_pipeline import apply_page_analysis
from relluna.services.pdf_decomposition import decompose_pdf


def _build_pdf_dm(pdf_path: Path) -> DocumentMemory:
    return DocumentMemory(
        version="v0.2.0",
        layer0=Layer0Custodia(
            documentid="rotated-compound-doc",
            contentfingerprint="c" * 64,
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
                    id="rotated-compound-doc",
                    tipo=ArtefatoTipo.original,
                    uri=str(pdf_path),
                    nome=pdf_path.name,
                    mimetype="application/pdf",
                    tamanho_bytes=pdf_path.stat().st_size,
                )
            ],
        ),
        layer2=Layer2Evidence(),
    )


def test_rotated_page_in_compound_pdf_keeps_subdocument_split_and_page_taxonomy(monkeypatch, tmp_path):
    pdf_path = tmp_path / "compound-rotated.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    dm = _build_pdf_dm(pdf_path)

    native_pages = [
        {
            "page": 1,
            "text": (
                "RECEITUARIO ORIENTACAO AO PACIENTE POSOLOGIA "
                "TOMAR 1 COMPRIMIDO AO DIA CRM 12345 PACIENTE MARIA SILVA "
            ) * 2,
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
    ]

    def fake_normalize_pdf_pages(*args, **kwargs):
        return [
            NormalizedPageImage(
                page=1,
                image_path=str(pdf_path),
                width=200,
                height=300,
                rotation_applied=0,
                source_pdf_rotation=0,
                orientation_score=0.0,
                warnings=[],
            ),
            NormalizedPageImage(
                page=2,
                image_path=str(pdf_path),
                width=300,
                height=200,
                rotation_applied=90,
                source_pdf_rotation=0,
                orientation_score=18.0,
                warnings=[],
            ),
        ]

    def fake_ocr_pages(page_images):
        assert [item["page"] for item in page_images] == [2]
        return [
            OCRPage(
                page=2,
                text="LAUDO EXAME IMPRESSAO DIAGNOSTICA",
                spans=[],
                width=200,
                height=300,
            )
        ]

    monkeypatch.setattr(decompose_pdf, "_extract_native_pdf_pages", lambda path: native_pages)
    monkeypatch.setattr(decompose_pdf, "normalize_pdf_pages", fake_normalize_pdf_pages)
    monkeypatch.setattr(decompose_pdf, "ocr_pages", fake_ocr_pages)

    dm = decompose_pdf.decompose_pdf_into_subdocuments(dm)
    dm = apply_page_analysis(dm)

    subdocs = json.loads(dm.layer2.sinais_documentais["subdocuments_v1"].valor)
    assert [(item["subdoc_id"], item["doc_type"], item["pages"]) for item in subdocs] == [
        ("subdoc_001", "RECEITUARIO", [1]),
        ("subdoc_002", "LAUDO_MEDICO", [2]),
    ]

    normalized_pages = json.loads(dm.layer2.sinais_documentais["normalized_pages_v1"].valor)
    assert normalized_pages[1]["rotation_applied"] == 90

    page_evidence = json.loads(dm.layer2.sinais_documentais["page_evidence_v1"].valor)
    assert [(item["page"], item["subdoc_id"], item["page_taxonomy"]["value"]) for item in page_evidence] == [
        (1, "subdoc_001", "receituario"),
        (2, "subdoc_002", "laudo_medico"),
    ]
