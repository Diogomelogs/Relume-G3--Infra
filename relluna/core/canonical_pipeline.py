from __future__ import annotations

import warnings

from relluna.core.document_memory import DocumentMemory, Layer4SemanticNormalization

def run_canonical_pipeline(dm: DocumentMemory) -> DocumentMemory:
    warnings.warn(
        "relluna.core.canonical_pipeline é legado; use o fluxo da API em "
        "relluna.services.ingestion.api.",
        DeprecationWarning,
        stacklevel=2,
    )
    if dm.layer4 is None:
        dm.layer4 = Layer4SemanticNormalization()

    # Exemplo mínimo REAL:
    # - se Layer2 tem data_exif confirmada => promove para data canônica
    # - se Layer3 tiver temporalidades => usa como fallback
    l2 = dm.layer2
    l3 = dm.layer3

    if l2 and getattr(l2, "data_exif", None) and l2.data_exif.valor:
        dm.layer4.data_canonica = l2.data_exif.valor  # ajuste para o tipo real do seu Layer4
        dm.layer4.fonte_data_canonica = "layer2.data_exif"

    elif l3 and getattr(l3, "estimativa_temporal", None) and l3.estimativa_temporal:
        dm.layer4.data_canonica = l3.estimativa_temporal.valor
        dm.layer4.fonte_data_canonica = "layer3.estimativa_temporal"

    return dm
