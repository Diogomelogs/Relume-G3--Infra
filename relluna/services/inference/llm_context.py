"""
Alias de compatibilidade para o módulo real de inferência L3.

Mantém o path antigo:
    relluna.services.inference.llm_context

Delegando para:
    relluna.services.context_inference.llm_context
"""

from relluna.services.context_inference.llm_context import (
    infer_layer3_from_layer2,
)

__all__ = ["infer_layer3_from_layer2"]
