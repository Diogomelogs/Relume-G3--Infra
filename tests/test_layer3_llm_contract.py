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
from relluna.core.document_memory.layer3 import (
    SemanticEntity,
    TemporalReference,
)
from relluna.core.document_memory.types_basic import (
    EvidenceRef,
    InferenceMeta,
    InferredDatetime,
)
from relluna.core.inference_pipeline import run_inference_pipeline


# ---------------------------------------------------------------------
# Helper: cria DM mínimo com Layer2 presente
# ---------------------------------------------------------------------
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
            artefatos=[
                ArtefatoBruto(
                    id="original",
                    tipo="original",
                    uri="/tmp/x.heic",
                )
            ],
        ),
    )

    dm.layer2 = Layer2Evidence()
    return dm


# ---------------------------------------------------------------------
# Teste principal: valida contrato de rastreabilidade da Layer3
# ---------------------------------------------------------------------
def test_layer3_llm_requires_lastro_and_meta(monkeypatch):
    from relluna.services.inference import llm_context

    # Mock da função real de inferência
    def _infer_from_l2(dm: DocumentMemory) -> Layer3Evidence:
        meta = InferenceMeta(
            engine="azure_openai",
            method="llm.json_schema",
        )

        l3 = Layer3Evidence()

        # Entidade semântica corretamente tipada
        l3.entidades_semanticas.append(
            SemanticEntity(
                tipo="documento",
                valor="laudo",
                score=0.9,
                lastro=[EvidenceRef(path="layer2.texto_ocr_literal")],
                meta=meta,
            )
        )

        # Temporalidade corretamente tipada
        l3.temporalidades_inferidas.append(
            TemporalReference(
                tipo="data_unica",
                inicio=InferredDatetime(valor="2024-02-24T00:00:00Z"),
                fim=None,
                confianca=0.8,
                lastro=[EvidenceRef(path="layer2.data_exif")],
                meta=meta,
            )
        )

        return l3

    # Monkeypatch no ponto correto
    monkeypatch.setattr(
        llm_context,
        "infer_layer3_from_layer2",
        _infer_from_l2,
    )

    dm = _dm_com_layer2()
    out = run_inference_pipeline(dm)

    # -----------------------------------------------------------------
    # Validações
    # -----------------------------------------------------------------
    assert out.layer3 is not None
    assert len(out.layer3.entidades_semanticas) == 1
    assert len(out.layer3.temporalidades_inferidas) == 1

    ent = out.layer3.entidades_semanticas[0]
    assert isinstance(ent, SemanticEntity)
    assert ent.lastro and ent.lastro[0].path == "layer2.texto_ocr_literal"
    assert ent.meta is not None
    assert ent.meta.engine == "azure_openai"

    tmp = out.layer3.temporalidades_inferidas[0]
    assert isinstance(tmp, TemporalReference)
    assert tmp.lastro and tmp.lastro[0].path == "layer2.data_exif"
    assert tmp.meta is not None
    assert tmp.meta.engine == "azure_openai"