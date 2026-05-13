from relluna.core.document_memory import DocumentMemory as DocumentMemory_v0_1_0
from relluna.core.document_memory import DocumentMemory_v0_2_0
from relluna.core.document_memory_v0_2_0 import DocumentMemory as ShimDocumentMemory_v0_2_0


def test_document_memory_v020_is_exported_without_replacing_v010():
    assert DocumentMemory_v0_1_0 is not DocumentMemory_v0_2_0
    assert DocumentMemory_v0_1_0.model_fields["version"].default == "v0.1.0"
    assert DocumentMemory_v0_2_0.model_fields["version"].default == "v0.2.0"


def test_v020_compatibility_shim_exports_canonical_document_memory():
    assert ShimDocumentMemory_v0_2_0 is DocumentMemory_v0_2_0
