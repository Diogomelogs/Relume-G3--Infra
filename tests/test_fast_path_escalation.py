from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from relluna.core.document_memory import (
    ArtefatoBruto,
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    Layer2Evidence,
    MediaType,
    OriginType,
    ProvenancedString,
)
from relluna.core.document_memory.layer1 import ArtefatoTipo
from relluna.services.ingestion import api


def _build_pdf_dm(pdf_path: Path) -> DocumentMemory:
    return DocumentMemory(
        version="v0.2.0",
        layer0=Layer0Custodia(
            documentid="fast-path-doc",
            contentfingerprint="d" * 64,
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
                    id="fast-path-doc",
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


@pytest.mark.asyncio
async def test_fast_path_does_not_escalate_for_simple_native_pdf_with_layout_spans(monkeypatch, tmp_path):
    pdf_path = tmp_path / "simple-native.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    dm = _build_pdf_dm(pdf_path)

    def fake_extract_basic(current: DocumentMemory) -> DocumentMemory:
        spans = [
            {"page": 1, "text": "Paciente: MARIA SILVA", "bbox": [10, 10, 150, 20]},
            {"page": 1, "text": "Prestador: DRA ANA LIMA", "bbox": [10, 30, 170, 40]},
            {"page": 1, "text": "CRM 12345", "bbox": [10, 50, 90, 60]},
            {"page": 1, "text": "Data: 05/03/2024", "bbox": [10, 70, 120, 80]},
            {"page": 1, "text": "CID S83.2", "bbox": [10, 90, 80, 100]},
        ]
        current.layer2.sinais_documentais["layout_spans_v1"] = ProvenancedString(
            valor=json.dumps(spans, ensure_ascii=False),
            fonte="pytest",
            metodo="fixture",
            estado="confirmado",
            confianca=1.0,
        )
        return current

    async def fail_standard_pipeline(_dm: DocumentMemory) -> DocumentMemory:
        raise AssertionError("standard pipeline should not run for simple native fast-path PDF")

    monkeypatch.setattr(
        api,
        "_collect_preflight_signals",
        lambda current: api.PreflightSignals(
            media_type=MediaType.documento.value,
            page_count=1,
            has_native_text=True,
            native_rotation=0,
            is_pdf=True,
            original_filename=current.layer0.original_filename,
        ),
    )
    monkeypatch.setattr(api, "extract_basic", fake_extract_basic)
    monkeypatch.setattr(api, "_run_standard_pipeline", fail_standard_pipeline)

    out = await api._run_extract_pipeline(dm)

    assert "page_evidence_v1" in out.layer2.sinais_documentais
    page_evidence = json.loads(out.layer2.sinais_documentais["page_evidence_v1"].valor)
    assert len(page_evidence) == 1
    assert page_evidence[0]["people"]["patient_name"] == "MARIA SILVA"
    assert page_evidence[0]["people"]["provider_name"] == "DRA ANA LIMA"

    stages = [event.etapa for event in out.layer0.processingevents]
    assert "processing_escalation" not in stages
