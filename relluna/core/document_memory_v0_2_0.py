# ============================================================
# Backward Compatibility Shim – v0.2.0
# ============================================================

from .document_memory import (
    DocumentMemory_v0_2_0 as DocumentMemory,
    DocumentMemory_v0_2_0 as DocumentMemory_v0_2_0,
    DocumentMemoryCanonical as DocumentMemoryCanonical,
)

__all__ = [
    "DocumentMemory",
    "DocumentMemory_v0_2_0",
    "DocumentMemoryCanonical",
]
