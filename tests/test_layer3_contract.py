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
    ConfidenceState,
)

from relluna.services.context_inference.document_taxonomy.apply import apply_document_taxonomy


def test_layer3_sets_tipo_documento_with_lastro():
    dm = DocumentMemory(
        version="v0.1.0",
        layer0=Layer0Custodia(
            documentid="doc",
            contentfingerprint="8" * 64,
            ingestiontimestamp=datetime.now(timezone.utc),
            ingestionagent="test",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="a",
                    tipo="original",
                    uri="/tmp/x.pdf",
                    metadados_nativos={},
                    logs_ingestao=[],
                )
            ],
        ),
        layer2=Layer2EvidenceBaseModel(
            texto_ocr_literal=ProvenancedString(
                valor="DANFE Nota Fiscal CHAVE DE ACESSO",
                fonte="ocr",
                metodo="stub",
                estado=ConfidenceState.confirmado,
                confianca=1.0,
            )
        ),
    )

    dm2 = apply_document_taxonomy(dm)

    assert dm2.layer3 is not None
    assert dm2.layer3.tipo_documento is not None
    assert dm2.layer3.tipo_documento.valor == "nota_fiscal"
    assert dm2.layer3.tipo_documento.lastro
    assert len(dm2.layer3.regras_aplicadas) >= 1


def test_layer3_does_not_mutate_other_layers():
    dm = DocumentMemory(
        version="v0.1.0",
        layer0=Layer0Custodia(
            documentid="doc",
            contentfingerprint="9" * 64,
            ingestiontimestamp=datetime.now(timezone.utc),
            ingestionagent="test",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="a",
                    tipo="original",
                    uri="/tmp/x.pdf",
                    metadados_nativos={},
                    logs_ingestao=[],
                )
            ],
        ),
        layer2=Layer2EvidenceBaseModel(),
    )

    dm2 = apply_document_taxonomy(dm)

    assert dm2.layer0 == dm.layer0
    assert dm2.layer1 == dm.layer1
    assert dm2.layer2 == dm.layer2
