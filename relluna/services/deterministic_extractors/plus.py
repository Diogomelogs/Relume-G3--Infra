from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
from PIL import Image

from relluna.core.document_memory import DocumentMemory, MediaType


FONTE = "deterministic_extractors.plus"


async def extract_plus(dm: DocumentMemory) -> DocumentMemory:
    if dm.layer1 is None or not dm.layer1.artefatos:
        return dm

    artefato = dm.layer1.artefatos[0]
    path = Path(artefato.uri)

    if dm.layer2 is None:
        return dm

    plus: Dict[str, Any] = {}

    if dm.layer1.midia == MediaType.imagem and path.exists():
        with Image.open(path) as img:
            plus["width"] = img.width
            plus["height"] = img.height

    plus["engine"] = FONTE

    dm.layer2.deterministic_plus = plus
    return dm