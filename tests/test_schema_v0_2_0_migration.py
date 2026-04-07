from relluna.core.basic_pipeline import run_basic_pipeline
from relluna.core.document_memory_v0_2_0 import DocumentMemory as DocumentMemory_v0_2_0

def test_current_dm_compatibility(sample_file):
    dm = run_basic_pipeline(sample_file)
    DocumentMemory_v0_2_0.model_validate(dm.model_dump(mode="json"))