from relluna.core.document_memory import (
    ArtefatoBruto,
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    MediaType,
    OriginType,
)
from relluna.core.document_memory.layer1 import ArtefatoTipo
from relluna.core.document_memory_v0_2_0 import DocumentMemory as DocumentMemory_v0_2_0


def _current_dm_minimal() -> DocumentMemory:
    return DocumentMemory(
        layer0=Layer0Custodia(
            documentid="compat-v010",
            contentfingerprint="3" * 64,
            ingestionagent="pytest",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="artifact-1",
                    tipo=ArtefatoTipo.original,
                    uri="memory://compat-v010.pdf",
                    hash_sha256="3" * 64,
                )
            ],
        ),
    )


def test_current_document_memory_dump_is_accepted_by_v020_contract():
    dm = _current_dm_minimal()
    validated = DocumentMemory_v0_2_0.model_validate(dm.model_dump(mode="json"))

    assert validated.layer0.documentid == "compat-v010"
    assert validated.layer1.midia == MediaType.documento
