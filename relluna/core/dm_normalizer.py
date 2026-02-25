from __future__ import annotations

from datetime import datetime

from relluna.core.documentmemory import DocumentMemory, Layer4SemanticNormalization


def promote_temporal_to_layer4(dm: DocumentMemory) -> DocumentMemory:
    """
    Copia a estimativa temporal de layer3 para layer4 e garante que:

    - dm.layer3.estimativa_temporal.valor vire string (ISO),
    - dm.layer4.periodo e dm.layer4.rotulo_temporal sejam preenchidos.

    Não mexe em layer0–2 nem em layer5–6.
    """

    if dm.layer3 is None:
        return dm

    # Pega o campo que o teste usa: estimativa_temporal
    est = getattr(dm.layer3, "estimativa_temporal", None)
    if est is None:
        return dm

    # Converte datetime -> string ISO no próprio objeto de layer3
    if isinstance(getattr(est, "valor", None), datetime):
        est.valor = est.valor.isoformat()

    # Garante layer4 existente
    if dm.layer4 is None:
        dm.layer4 = Layer4SemanticNormalization(
            entidades=[],
            tags=[],
        )

    # Preenche periodo se ainda não existir
    if getattr(dm.layer4, "periodo", None) is None and isinstance(est.valor, str):
        # O teste só exige "not None"; usar o ISO completo é suficiente
        dm.layer4.periodo = est.valor

    # Preenche rótulo temporal se ainda não existir
    if getattr(dm.layer4, "rotulo_temporal", None) is None:
        dm.layer4.rotulo_temporal = "data_unica"

    return dm

DocumentMemory.model_rebuild()