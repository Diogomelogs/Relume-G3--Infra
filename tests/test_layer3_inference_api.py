# FILE: tests/test_layer3_inference_api.py
# (optional but recommended; keeps Layer4/6 untouched; verifies endpoint-style behavior if you wire it later)
# If you don't want extra tests yet, skip this file.

from __future__ import annotations

from datetime import datetime

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


def test_infer_layer3_sets_tipo_evento_for_recibo():
    dm = DocumentMemory(
        version="v0.1.0",
        layer0=Layer0Custodia(
            documentid="doc-3",
            contentfingerprint="hash-3",
            ingestiontimestamp=datetime.utcnow(),
            ingestionagent="test",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[ArtefatoBruto(id="a3", tipo="original", uri="/tmp/r.pdf")],
        ),
        layer2=Layer2EvidenceBaseModel(
            texto_ocr_literal=ProvenancedString(
                valor="Recibo do bilhete eletrônico",
                fonte="deterministic",
                metodo="ocr_stub",
                estado=ConfidenceState.confirmado,
            )
        ),
    )

    out = infer_layer3(dm)
    assert out.layer3 is not None
    assert out.layer3.tipo_evento is not None
    assert out.layer3.tipo_evento.valor == "recibo"
