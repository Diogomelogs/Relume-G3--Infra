import uuid
from datetime import datetime, UTC
import copy

from relluna.core.document_memory import (
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    ArtefatoBruto,
    MediaType,
    OriginType,
    Layer2Evidence,
)
from relluna.core.full_pipeline import run_full_pipeline


def _dm_com_layer2() -> DocumentMemory:
    dm = DocumentMemory(
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
    dm.layer2 = Layer2Evidence.model_validate(
        {
            "largura_px": {
                "valor": 100.0,
                "fonte": "deterministic_extractors.basic",
                "metodo": "Pillow.size",
                "estado": "confirmado",
                "confianca": 1.0,
                "lastro": [],
            }
        }
    )
    return dm


def test_full_pipeline_does_not_mutate_layer2(monkeypatch):
    # Evita que basic_pipeline sobrescreva Layer2 no teste
    from relluna.core import basic_pipeline
    monkeypatch.setattr(basic_pipeline, "run_basic_pipeline", lambda dm: dm)

    # Evita chamadas reais de LLM/embeddings
    from relluna.core import inference_pipeline, canonical_pipeline, archival_pipeline, semantic_pipeline
    monkeypatch.setattr(inference_pipeline, "run_inference_pipeline", lambda dm: dm)
    monkeypatch.setattr(canonical_pipeline, "run_canonical_pipeline", lambda dm: dm)
    monkeypatch.setattr(archival_pipeline, "run_archival_pipeline", lambda dm: dm)
    monkeypatch.setattr(semantic_pipeline, "run_semantic_pipeline", lambda dm: dm)

    dm = _dm_com_layer2()
    before = copy.deepcopy(dm.layer2.model_dump())

    out = run_full_pipeline(dm, stage="full")

    after = out.layer2.model_dump()
    assert before == after