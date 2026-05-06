from __future__ import annotations

from relluna.core.document_memory import DocumentMemory


FONTE = "services.legal.legal_pipeline_v2"
PIPELINE_ROLE = "compatibility_noop"


def apply_legal_extraction(dm: DocumentMemory) -> DocumentMemory:
    """
    Hook mínimo e explícito de compatibilidade.

    Layer2 não deve receber classificação jurídica nem canonização contextual,
    então esta etapa permanece intencionalmente sem mutação semântica.

    O caminho vivo continua chamando este módulo para manter a esteira estável
    e rastreável, mas o processamento jurídico real deve consumir sinais já
    consolidados em Layer2/Layer3/read models.

    A classificação de tipo documental e a composição contextual devem ocorrer
    em Layer3 via `infer_layer3`.
    """
    return dm
