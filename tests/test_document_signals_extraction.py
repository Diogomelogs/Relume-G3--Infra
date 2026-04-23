from datetime import datetime, timezone

from relluna.core.document_memory import (
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    ArtefatoBruto,
    MediaType,
    OriginType,
    Layer2EvidenceBaseModel,
    ProvenancedString,
    ProvenancedNumber,
    ConfidenceState,
)

from relluna.services.context_inference.document_taxonomy.signals import (
    extract_document_signals,
)


def test_extract_signals_from_pdf_with_ocr():
    dm = DocumentMemory(
        version="v0.1.0",
        layer0=Layer0Custodia(
            documentid="doc1",
            contentfingerprint="1" * 64,
            ingestiontimestamp=datetime.now(timezone.utc),
            ingestionagent="test",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="a1",
                    tipo="original",
                    uri="/tmp/recibo.pdf",
                    metadados_nativos={},
                    logs_ingestao=[],
                )
            ],
        ),
        layer2=Layer2EvidenceBaseModel(
            texto_ocr_literal=ProvenancedString(
                valor="Recibo CPF 123.456.789-00 valor R$ 100,00",
                fonte="ocr",
                metodo="stub",
                estado=ConfidenceState.confirmado,
            ),
            num_paginas=ProvenancedNumber(
                valor=1,
                fonte="pdf",
                metodo="stub",
                estado=ConfidenceState.confirmado,
            ),
        ),
    )

    signals = extract_document_signals(dm)

    assert signals.media_type == "documento"
    assert signals.file_extension == "pdf"
    assert signals.has_text is True
    assert signals.has_currency is True
    assert signals.has_identifiers is True
    assert signals.num_pages == 1


def test_extract_signals_from_image():
    dm = DocumentMemory(
        version="v0.1.0",
        layer0=Layer0Custodia(
            documentid="doc2",
            contentfingerprint="2" * 64,
            ingestiontimestamp=datetime.now(timezone.utc),
            ingestionagent="test",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.imagem,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="a2",
                    tipo="original",
                    uri="/tmp/foto.jpg",
                    metadados_nativos={},
                    logs_ingestao=[],
                )
            ],
        ),
        layer2=Layer2EvidenceBaseModel(
            largura_px=ProvenancedNumber(
                valor=1920,
                fonte="exif",
                metodo="stub",
                estado=ConfidenceState.confirmado,
            ),
            altura_px=ProvenancedNumber(
                valor=1080,
                fonte="exif",
                metodo="stub",
                estado=ConfidenceState.confirmado,
            ),
        ),
    )

    signals = extract_document_signals(dm)

    assert signals.media_type == "imagem"
    assert signals.file_extension == "jpg"
    assert signals.width_px == 1920
    assert signals.height_px == 1080
