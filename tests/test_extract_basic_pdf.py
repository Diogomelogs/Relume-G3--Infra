from pathlib import Path

from pypdf import PdfWriter

from relluna.core.document_memory import (
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    ArtefatoBruto,
    MediaType,
    OriginType,
    ConfidenceState,
)
from relluna.services.deterministic_extractors.basic import extract_basic
from datetime import datetime


def _build_minimal_pdf_dm(pdf_path: Path) -> DocumentMemory:
    layer0 = Layer0Custodia(
        documentid="test-pdf-docid",
        contentfingerprint="dummy-hash-pdf",
        ingestiontimestamp=datetime.utcnow(),
        ingestionagent="test_ingest_pdf",
    )

    artefato = ArtefatoBruto(
        id=pdf_path.name,
        tipo="original",
        uri=str(pdf_path),
        metadados_nativos={},
    )

    layer1 = Layer1Artefatos(
        midia=MediaType.documento,
        origem=OriginType.digital_nativo,
        artefatos=[artefato],
    )

    return DocumentMemory(
        layer0=layer0,
        layer1=layer1,
    )


def test_extract_basic_pdf_populates_layer2(tmp_path: Path):
    # 1) Cria um PDF simples com 2 páginas em branco
    pdf_path = tmp_path / "teste.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    with pdf_path.open("wb") as f:
        writer.write(f)

    assert pdf_path.exists()

    # 2) Constrói o DM mínimo para esse PDF
    dm = _build_minimal_pdf_dm(pdf_path)

    # 3) Roda o extrator
    dm_out = extract_basic(dm)
    layer2 = dm_out.layer2
    assert layer2 is not None

    # 4) num_paginas deve ser 2, confirmado
    assert layer2.num_paginas is not None
    assert layer2.num_paginas.valor == 2.0
    assert layer2.num_paginas.estado == ConfidenceState.confirmado

    # 5) Como o PDF é só páginas em branco, texto_ocr_literal deve ser insuficiente
    assert layer2.texto_ocr_literal is not None
    assert layer2.texto_ocr_literal.valor in (None, "")
    assert layer2.texto_ocr_literal.estado == ConfidenceState.insuficiente
