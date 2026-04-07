"""
Namespace de compatibilidade para serviços de inferência.

Mantém o path legado:
    relluna.services.inference

Hoje delega para:
    relluna.services.context_inference.llm_context
"""

from . import llm_context

__all__ = ["llm_context"]
