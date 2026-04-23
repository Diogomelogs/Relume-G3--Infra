# FILE: tests/test_layer3_inference_contract.py
# (new; contract tests for lastro + immutability + non-hallucination)

from __future__ import annotations

from copy import deepcopy
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
from relluna.services.context_inference.basic import infer_layer3


def _make_dm_with_ocr(ocr_text: str) -> DocumentMemory:
    layer0 = Layer0Custodia(
        documentid="doc-1",
        contentfingerprint="a" * 64,
        ingestiontimestamp=datetime.now(timezone.utc),
        ingestionagent="test",
    )

    layer1 = Layer1Artefatos(
        midia=MediaType.documento,
        origem=OriginType.digital_nativo,
        artefatos=[
            ArtefatoBruto(
                id="a1",
                tipo="original",
                uri="/tmp/x.pdf",
                metadados_nativos={},
                logs_ingestao=[],
            )
        ],
    )

    layer2 = Layer2EvidenceBaseModel(
        texto_ocr_literal=ProvenancedString(
            valor=ocr_text,
            fonte="deterministic_extractors.basic",
            metodo="ocr_stub",
            estado=ConfidenceState.confirmado,
            confianca=1.0,
        )
    )

    return DocumentMemory(version="v0.1.0", layer0=layer0, layer1=layer1, layer2=layer2)


def test_layer3_requires_lastro_for_filled_fields():
    dm = _make_dm_with_ocr("Recibo do bilhete eletrônico 03/06/2024")
    dm2 = infer_layer3(dm)

    assert dm2.layer3 is not None
    assert dm2.layer3.tipo_evento is not None
    assert dm2.layer3.tipo_evento.lastro is not None
    assert len(dm2.layer3.tipo_evento.lastro) >= 1

    # O contrato atual permite lastro via sinais canônicos intermediários.
    paths = [getattr(e, "source_path", None) or getattr(e, "path", None) for e in dm2.layer3.tipo_evento.lastro]
    assert any(path and path.startswith("layer2.") for path in paths)


def test_layer3_does_not_mutate_layer0_layer1_layer2():
    dm = _make_dm_with_ocr("Recibo 03/06/2024")
    before = dm.model_dump(mode="python")

    dm2 = infer_layer3(dm)
    after = dm2.model_dump(mode="python")

    # Only layer3 may change
    assert after["layer0"] == before["layer0"]
    assert after["layer1"] == before["layer1"]
    assert after["layer2"] == before["layer2"]


def test_layer3_no_hallucination_when_no_evidence():
    layer0 = Layer0Custodia(
        documentid="doc-2",
        contentfingerprint="b" * 64,
        ingestiontimestamp=datetime.now(timezone.utc),
        ingestionagent="test",
    )

    layer1 = Layer1Artefatos(
        midia=MediaType.imagem,
        origem=OriginType.digital_nativo,
        artefatos=[
            ArtefatoBruto(
                id="a2",
                tipo="original",
                uri="/tmp/x.jpg",
                metadados_nativos={},
                logs_ingestao=[],
            )
        ],
    )

    dm = DocumentMemory(version="v0.1.0", layer0=layer0, layer1=layer1, layer2=Layer2EvidenceBaseModel())
    dm2 = infer_layer3(dm)

    # No evidence -> may create the container, but must not infer content.
    assert dm2.layer3 is not None
    assert dm2.layer3.tipo_evento is None
    assert dm2.layer3.tipo_documento is None
    assert dm2.layer3.eventos_probatorios == []
