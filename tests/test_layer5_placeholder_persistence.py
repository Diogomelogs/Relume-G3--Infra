from __future__ import annotations

from relluna.core.contracts.mappers import to_contract
from relluna.core.document_memory import (
    ArtefatoBruto,
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    MediaType,
    OriginType,
)
from relluna.core.document_memory.layer1 import ArtefatoTipo
from relluna.services.derivatives.layer5 import apply_layer5


def _dm(midia: MediaType = MediaType.documento) -> DocumentMemory:
    return DocumentMemory(
        layer0=Layer0Custodia(
            documentid="layer5-placeholder-test",
            contentfingerprint="4" * 64,
            ingestionagent="pytest",
        ),
        layer1=Layer1Artefatos(
            midia=midia,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="artifact-layer5-placeholder-test",
                    tipo=ArtefatoTipo.original,
                    uri="memory://layer5-placeholder-test.pdf",
                )
            ],
        ),
    )


def test_apply_layer5_persists_read_models_in_document_memory():
    dm = apply_layer5(_dm())

    assert dm.layer5 is not None
    assert dm.layer5.persistence_state == "stored"
    assert len(dm.layer5.storage_uris) == 3
    assert all(item.kind == "document_memory" for item in dm.layer5.storage_uris)
    assert all(item.uri.startswith("document-memory://") for item in dm.layer5.storage_uris)
    assert dm.layer5.documentos_derivados[0].uri.startswith("generated://")


def test_layer5_contract_exposes_stored_state_without_fake_blob_uri():
    contract = to_contract(apply_layer5(_dm(MediaType.imagem)))

    assert contract["layer5"]["persistence_state"] == "stored"
    assert len(contract["layer5"]["storage_uris"]) == 3
    assert all(item["kind"] == "document_memory" for item in contract["layer5"]["storage_uris"])
    assert contract["layer5"]["imagens_derivadas"][0]["uri"].startswith("generated://")


def test_layer5_contract_reports_stored_state_with_explicit_local_storage_contract():
    contract = to_contract(apply_layer5(_dm()))

    assert contract["layer5"]["persistence_state"] == "stored"
    assert contract["layer5"]["storage_uris"]
