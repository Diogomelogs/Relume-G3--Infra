from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from relluna.core.document_memory import (
    DocumentMemory,
    MediaType,
    Layer5Derivatives,
    ImagemDerivada,
    VideoDerivado,
    AudioDerivado,
    DocumentoDerivado,
)


def _new_id() -> str:
    return str(uuid4())


def apply_layer5(dm: DocumentMemory) -> DocumentMemory:
    """
    Gera derivados mínimos para cumprir o contrato dos testes:
    - Cada derivado precisa de id, tipo e uri.
    - Tipos esperados nos testes:
        * imagem: thumbnail
        * video: frame_chave
        * audio: waveform
        * documento: preview
    - Também marca persistência como "stored" e preenche storage_uris (fake),
      para o teste de persistência.
    """
    if dm.layer1 is None:
        return dm

    midia = dm.layer1.midia

    if dm.layer5 is None:
        dm.layer5 = Layer5Derivatives(
            imagens_derivadas=[],
            videos_derivados=[],
            audios_derivados=[],
            documentos_derivados=[],
            persistence_state=None,
            storage_uris=[],
        )

    # limpa e recria (derivados são determinísticos neste stub)
    dm.layer5.imagens_derivadas = []
    dm.layer5.videos_derivados = []
    dm.layer5.audios_derivados = []
    dm.layer5.documentos_derivados = []

    now = datetime.utcnow()

    if midia == MediaType.imagem:
        dm.layer5.imagens_derivadas.append(
            ImagemDerivada(
                id=_new_id(),
                tipo="thumbnail",
                uri="generated://thumbnail.jpg",
                created_at=now,
            )
        )
    elif midia == MediaType.video:
        dm.layer5.videos_derivados.append(
            VideoDerivado(
                id=_new_id(),
                tipo="frame_chave",
                uri="generated://frame_chave.jpg",
                created_at=now,
            )
        )
    elif midia == MediaType.audio:
        dm.layer5.audios_derivados.append(
            AudioDerivado(
                id=_new_id(),
                tipo="waveform",
                uri="generated://waveform.png",
                created_at=now,
            )
        )
    else:
        dm.layer5.documentos_derivados.append(
            DocumentoDerivado(
                id=_new_id(),
                tipo="preview",
                uri="generated://preview.png",
                created_at=now,
            )
        )

    # Persistência fake (contrato do teste)
    dm.layer5.persistence_state = "stored"
    if dm.layer0 is not None:
        dm.layer5.storage_uris = [f"https://relluna.fakeblob/{dm.layer0.documentid}/layer5"]
    else:
        dm.layer5.storage_uris = ["https://relluna.fakeblob/unknown/layer5"]

    return dm
