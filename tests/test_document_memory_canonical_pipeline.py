# tests/test_document_memory_canonical_pipeline.py

from relluna.core.document_memory import DocumentMemory_v0_2_0

from tests.conftest import sample_file  # se já existir algo assim

def test_pipeline_produz_dm_canonico(sample_file):
    dm_old = run_basic_pipeline(sample_file)  # DM no formato atual
    dm_json = dm_old.model_dump(mode="json")

    dm_new = DocumentMemory_v0_2_0.model_validate(dm_json)

    assert dm_new.layer0 is not None
    # se quiser forçar algo de layer5/6:
    # assert dm_new.layer5 is not None
