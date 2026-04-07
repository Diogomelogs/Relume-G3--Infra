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
    Layer4SemanticNormalization,
    Layer6Optimization,
)
from relluna.core.full_pipeline import run_full_pipeline


def _dm_minimo() -> DocumentMemory:
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


@pytest.fixture()
def patch_pipelines(monkeypatch):
    # Evita I/O e dependências: basic cria Layer2, outros criam camadas vazias.
    from relluna.core import basic_pipeline
    from relluna.core import inference_pipeline
    from relluna.core import canonical_pipeline
    from relluna.core import archival_pipeline
    from relluna.core import semantic_pipeline

    def _basic(dm):
        dm.layer2 = Layer2Evidence()
        return dm

    def _infer(dm):
        if dm.layer3 is None:
            dm.layer3 = Layer3Evidence()
        return dm

    def _canon(dm):
        if dm.layer4 is None:
            dm.layer4 = Layer4SemanticNormalization()
        return dm

    def _arch(dm):
        if getattr(dm, "layer5", None) is None:
            dm.layer5 = {}
        return dm

    def _sem(dm):
        if dm.layer6 is None:
            dm.layer6 = Layer6Optimization()
        return dm

    monkeypatch.setattr(basic_pipeline, "run_basic_pipeline", _basic)
    monkeypatch.setattr(inference_pipeline, "run_inference_pipeline", _infer)
    monkeypatch.setattr(canonical_pipeline, "run_canonical_pipeline", _canon)
    monkeypatch.setattr(archival_pipeline, "run_archival_pipeline", _arch)
    monkeypatch.setattr(semantic_pipeline, "run_semantic_pipeline", _sem)


@pytest.mark.parametrize(
    "stage, expect_l3, expect_l4, expect_l5, expect_l6",
    [
        ("basic", False, False, False, False),
        ("plus", True, False, False, False),
        ("canonical", True, True, False, False),
        ("archival", True, True, True, False),
        ("full", True, True, True, True),
    ],
)
def test_full_pipeline_stage_matrix(patch_pipelines, stage, expect_l3, expect_l4, expect_l5, expect_l6):
    dm = _dm_minimo()
    out = run_full_pipeline(dm, stage=stage)

    assert out.layer2 is not None

    assert (out.layer3 is not None) == expect_l3
    assert (getattr(out, "layer4", None) is not None) == expect_l4
    assert (getattr(out, "layer5", None) is not None) == expect_l5
    assert (getattr(out, "layer6", None) is not None) == expect_l6