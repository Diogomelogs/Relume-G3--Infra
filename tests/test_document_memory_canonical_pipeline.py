from relluna.core.document_memory import (
    DocumentMemory,
    DocumentMemory_v0_2_0,
    Layer0Custodia,
)


def test_current_minimal_dm_can_be_projected_to_v020_contract():
    dm_old = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="pipeline-contract",
            contentfingerprint="5" * 64,
            ingestionagent="pytest",
        )
    )

    dm_new = DocumentMemory_v0_2_0.model_validate(dm_old.model_dump(mode="json"))

    assert dm_old.version == "v0.1.0"
    assert dm_new.layer0.documentid == "pipeline-contract"
