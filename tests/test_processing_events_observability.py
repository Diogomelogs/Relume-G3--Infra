import json
from pathlib import Path

import pytest

from relluna.core.document_memory import (
    ArtefatoBruto,
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    Layer2Evidence,
    OriginType,
    ProvenancedString,
)
from relluna.core.document_memory.layer1 import ArtefatoTipo, MediaType
from relluna.services.ingestion import api
from relluna.services.page_extraction.page_pipeline import apply_page_analysis
from relluna.services.pdf_decomposition import decompose_pdf
from relluna.services.page_extraction.page_normalizer import NormalizedPageImage
from relluna.services.page_extraction.page_ocr import OCRPage


def _build_pdf_dm(pdf_path: Path) -> DocumentMemory:
    return DocumentMemory(
        layer0=Layer0Custodia(
            documentid="doc-observability",
            contentfingerprint="b" * 64,
            ingestionagent="pytest",
            processingevents=[],
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digitalizado_analogico,
            artefatos=[
                ArtefatoBruto(
                    id="artifact-observability",
                    tipo=ArtefatoTipo.original,
                    uri=str(pdf_path),
                )
            ],
        ),
        layer2=Layer2Evidence(),
    )


@pytest.mark.asyncio
async def test_api_stage_processing_events_include_duration_for_critical_stages(tmp_path):
    dm = _build_pdf_dm(tmp_path / "doc.pdf")

    async def passthrough():
        return dm

    for stage in [
        "extract_basic",
        "apply_page_analysis",
        "apply_entities_canonical_v1",
        "timeline_seed_v2",
        "infer_layer3",
    ]:
        dm = await api._run_stage(dm, stage, "pytest.engine", passthrough)

    events = {
        event.etapa: event
        for event in dm.layer0.processingevents
    }
    for stage in [
        "extract_basic",
        "apply_page_analysis",
        "apply_entities_canonical_v1",
        "timeline_seed_v2",
        "infer_layer3",
    ]:
        assert events[stage].status == "success"
        assert isinstance(events[stage].detalhes["duration_ms"], float)
        assert events[stage].detalhes["duration_ms"] >= 0.0


def test_decompose_pdf_records_page_observability(monkeypatch, tmp_path):
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    dm = _build_pdf_dm(pdf_path)

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
    monkeypatch.setattr(
        decompose_pdf,
        "normalize_pdf_pages",
        lambda *args, **kwargs: [
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
                        "message": "timeout",
                        "engine": "tesseract",
                        "page": 1,
                    }
                ],
            )
        ],
    )
    monkeypatch.setattr(
        decompose_pdf,
        "ocr_pages",
        lambda page_images: [
            OCRPage(
                page=1,
                text="",
                spans=[],
                width=200,
                height=200,
                warnings=[
                    {
                        "code": "ocr_page_timeout",
                        "severity": "warning",
                        "message": "timeout",
                        "engine": "tesseract",
                        "page": 1,
                    }
                ],
            )
        ],
    )

    decompose_pdf.decompose_pdf_into_subdocuments(dm)

    by_stage = {
        (event.etapa, event.detalhes.get("warning_code")): event
        for event in dm.layer0.processingevents
    }

    normalization = by_stage[("page_normalization", "ocr_orientation_timeout")]
    assert normalization.status == "warning"
    assert normalization.detalhes["page_index"] == 1
    assert normalization.detalhes["degraded_mode"] == "orientation_degraded"
    assert isinstance(normalization.detalhes["duration_ms"], float)

    ocr = by_stage[("page_ocr", "ocr_page_timeout")]
    assert ocr.status == "warning"
    assert ocr.detalhes["page_index"] == 1
    assert ocr.detalhes["degraded_mode"] == "ocr_page_degraded"
    assert isinstance(ocr.detalhes["duration_ms"], float)


def test_page_analysis_records_page_index_and_warning_code(tmp_path):
    dm = _build_pdf_dm(tmp_path / "native.pdf")
    dm.layer2.texto_ocr_literal = ProvenancedString(
        valor="PAGINA 1\ntexto sem marcador clinico\n\nPAGINA 2\nPaciente: MARCOS ANTONIO REIS\nData: 05/03/2024",
        fonte="test",
        metodo="fixture",
        estado="confirmado",
        confianca=1.0,
    )
    dm.layer2.sinais_documentais["subdocuments_v1"] = ProvenancedString(
        valor=json.dumps(
            [
                {
                    "subdoc_id": "subdoc_001",
                    "doc_type": "DOCUMENTO",
                    "page_map": [
                        {"page": 1, "text": "texto sem marcador clinico"},
                        {
                            "page": 2,
                            "text": "Paciente: MARCOS ANTONIO REIS\nData: 05/03/2024",
                        },
                    ],
                }
            ]
        ),
        fonte="test",
        metodo="fixture",
        estado="confirmado",
        confianca=1.0,
    )

    apply_page_analysis(dm)

    page_events = [
        event
        for event in dm.layer0.processingevents
        if event.etapa == "page_analysis"
    ]
    assert [event.detalhes["page_index"] for event in page_events] == [1, 2]
    assert all(isinstance(event.detalhes["duration_ms"], float) for event in page_events)
    assert page_events[0].status == "warning"
    assert page_events[0].detalhes["warning_code"] == "page_analysis_no_anchors"
