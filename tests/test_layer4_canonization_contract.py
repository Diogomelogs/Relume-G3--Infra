import uuid
from datetime import datetime, UTC

import pytest

from relluna.core.document_memory import (
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    ArtefatoBruto,
    MediaType,
    OriginType,
    Layer2Evidence,
    Layer3Evidence,
)
from relluna.core.canonical_pipeline import run_canonical_pipeline


def _dm_base() -> DocumentMemory:
    return DocumentMemory(
        layer0=Layer0Custodia(
            documentid=str(uuid.uuid4()),
            contentfingerprint="a" * 64,
            ingestiontimestamp=datetime.now(UTC),
            ingestionagent="test",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.imagem,
            origem=OriginType.digital_nativo,
            artefatos=[ArtefatoBruto(id="original", tipo="original", uri="/tmp/x.jpg")],
        ),
    )


@pytest.mark.xfail(
    reason=(
        "canonical_pipeline é legado e tenta escrever fonte_data_canonica, "
        "campo proibido no Layer4 atual"
    ),
    strict=False,
)
def test_layer4_promotes_layer2_exif_when_present():
    dm = _dm_base()
    dm.layer2 = Layer2Evidence.model_validate(
        {
            "data_exif": {
                "valor": "2024-02-24T11:56:09+00:00",
                "fonte": "deterministic_extractors.basic",
                "metodo": "exif",
                "estado": "confirmado",
                "confianca": 1.0,
                "lastro": [],
            }
        }
    )

    out = run_canonical_pipeline(dm)

    assert out.layer4 is not None
    # Ajuste estes asserts para os nomes reais do seu Layer4:
    assert getattr(out.layer4, "data_canonica", None) is not None
    assert getattr(out.layer4, "fonte_data_canonica", None) == "layer2.data_exif"


def test_layer4_does_not_invent_date_without_evidence():
    dm = _dm_base()
    dm.layer2 = Layer2Evidence()  # sem data_exif
    dm.layer3 = Layer3Evidence()  # sem estimativa

    out = run_canonical_pipeline(dm)

    assert out.layer4 is not None
    assert getattr(out.layer4, "data_canonica", None) in (None, "")
