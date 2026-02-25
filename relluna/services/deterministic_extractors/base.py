from relluna.core.document_memory.layer2 import Layer2Evidence


def extract_base(dm):
    """
    Extrator mínimo universal.
    Deve ser chamado ANTES de qualquer extrator específico.
    """

    # Garantir que layer2 exista e seja o modelo correto
    if dm.layer2 is None or not isinstance(dm.layer2, Layer2Evidence):
        dm.layer2 = Layer2Evidence()

    return dm