from datetime import datetime
from relluna.core.document_memory import (
    DocumentMemory,
    Layer4SemanticNormalization,
)


def promote_temporal_to_layer4(dm: DocumentMemory) -> DocumentMemory:
    """
    Copia estimativa temporal de layer3 para layer4.

    Regras esperadas pelos testes:
    - layer3.estimativa_temporal.valor pode virar string ISO.
    - layer4.data_canonica deve ser datetime.
    - layer4.periodo deve ser 'YYYY-MM-DD'.
    - NÃO escrever em rotulo_temporal (é property).
    """

    if dm.layer3 is None or dm.layer3.estimativa_temporal is None:
        return dm

    est = dm.layer3.estimativa_temporal
    valor = est.valor

    # Normaliza layer3 para string ISO
    if isinstance(valor, datetime):
        est.valor = valor.isoformat()
        dt = valor
    elif isinstance(valor, str):
        try:
            dt = datetime.fromisoformat(valor)
        except Exception:
            return dm
    else:
        return dm

    # Garante layer4
    if dm.layer4 is None:
        dm.layer4 = Layer4SemanticNormalization(
            entidades=[],
            tags=[],
        )

    # Preenche data_canonica (datetime)
    if dm.layer4.data_canonica is None:
        dm.layer4.data_canonica = dt

    # Preenche periodo (string YYYY-MM-DD)
    if dm.layer4.periodo is None:
        dm.layer4.periodo = dt.date().isoformat()

    return dm
