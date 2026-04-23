import uuid
from datetime import datetime, UTC

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
from relluna.core.semantic_pipeline import run_semantic_pipeline


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


def test_layer6_noop_when_no_text_and_no_entities(monkeypatch):
    from relluna.infra.azure_openai import client as aoai

    called = {"n": 0}

    def _fake_embed(text: str):
        called["n"] += 1
        return [0.0, 0.0, 0.0]

    monkeypatch.setattr(aoai, "embed_text", _fake_embed)

    dm = _dm_base()
    dm.layer2 = Layer2Evidence()  # sem texto OCR
    dm.layer3 = Layer3Evidence()  # sem entidades

    out = run_semantic_pipeline(dm)

    assert called["n"] == 0
    assert getattr(out, "layer6", None) is None or getattr(out.layer6, "embeddings_base", None) in (None, [])


def test_layer6_embeds_when_ocr_text_exists(monkeypatch):
    from relluna.infra.azure_openai import client as aoai

    called = {"n": 0}

    def _fake_embed(text: str):
        called["n"] += 1
        assert len(text) > 0
        return [1.0, 2.0, 3.0]

    monkeypatch.setattr(aoai, "embed_text", _fake_embed)

    dm = _dm_base()
    dm.layer2 = Layer2Evidence.model_validate(
        {
            "texto_ocr_literal": {
                "valor": "LAUDO MÉDICO 24/02/2024",
                "fonte": "deterministic_extractors.basic",
                "metodo": "ocr",
                "estado": "confirmado",
                "confianca": 1.0,
                "lastro": [],
            }
        }
    )

    out = run_semantic_pipeline(dm)

    assert called["n"] == 1
    assert out.layer6 is not None
    assert getattr(out.layer6, "embeddings_base", None) == [1.0, 2.0, 3.0]
