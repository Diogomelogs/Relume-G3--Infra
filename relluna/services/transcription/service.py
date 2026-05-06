from __future__ import annotations

"""
Shim de compatibilidade para transcrição.

O caminho vivo usa `relluna.services.transcription.asr`.
Este módulo existe apenas para imports legados e reexporta a API mínima usada
em runtime/testes sem manter placeholder quebrado no pacote.
"""

from .asr import ASROptions, apply_transcription_to_layer2, get_asr_options_from_env

__all__ = [
    "ASROptions",
    "apply_transcription_to_layer2",
    "get_asr_options_from_env",
]
