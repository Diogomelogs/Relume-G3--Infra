from __future__ import annotations

import warnings

from .models_v0_2_0 import (
    DocumentMemoryCanonical,
    DocumentMemory_v0_2_0,
    DocumentMemory as CanonicalDocumentMemory,
)

warnings.warn(
    "relluna.core.document_memory.models é um shim legado; use "
    "relluna.core.document_memory ou relluna.core.document_memory.models_v0_2_0.",
    DeprecationWarning,
    stacklevel=2,
)

DocumentMemory = CanonicalDocumentMemory

__all__ = [
    "DocumentMemory",
    "DocumentMemoryCanonical",
    "DocumentMemory_v0_2_0",
]
