from __future__ import annotations

from typing import Optional

from relluna.core.document_memory import DocumentMemory  # type: ignore[import]


def _safe_get(obj: object, attr: str) -> Optional[object]:
    return getattr(obj, attr, None) if obj is not None else None


def generate_factual_narrative(dm: DocumentMemory) -> str:
    """
    Narrativa factual mínima, derivada apenas de Layers 1–4.

    Não persiste nada, não altera o DM.
    """

    layer0 = _safe_get(dm, "layer0")
    layer1 = _safe_get(dm, "layer1")
    layer3 = _safe_get(dm, "layer3")
    layer4 = _safe_get(dm, "layer4")

    midia = _safe_get(layer1, "midia")
    origem = _safe_get(layer1, "origem")
    data_canonica = _safe_get(layer4, "datacanonica")
    tipo_evento = _safe_get(layer3, "tipo_evento")

    partes: list[str] = []

    # Quem / o que
    if midia is not None:
        partes.append(f"Memória do tipo {midia}.")
    else:
        partes.append("Memória de tipo não identificado.")

    # Quando
    if data_canonica:
        partes.append(f"Registrada em {data_canonica}.")
    else:
        partes.append("Sem data canônica confirmada.")

    # Origem
    if origem is not None:
        partes.append(f"Origem do artefato: {origem}.")
    else:
        partes.append("Origem do artefato não determinada.")

    # Tipo de evento / documento
    if tipo_evento:
        partes.append(f"Classificada como evento ou documento do tipo {tipo_evento}.")
    else:
        partes.append("Tipo de evento ou documento ainda não classificado.")

    # Observação de incerteza explícita
    partes.append(
        "Algumas informações de contexto podem estar ausentes; "
        "esta narrativa foi gerada apenas a partir de dados estruturados do documento."
    )

    return " ".join(partes)


class Layer6Forensic:
    """
    Wrapper legado para compatibilidade com imports antigos.

    Uso novo recomendado: generate_factual_narrative(dm).
    """

    def __init__(self, dm: DocumentMemory) -> None:
        self.dm = dm

    def narrative(self) -> str:
        return generate_factual_narrative(self.dm)
