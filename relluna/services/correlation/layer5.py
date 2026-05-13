from __future__ import annotations

from relluna.core.document_memory import DocumentMemory, MediaType
from relluna.core.contracts.document_memory_contract import (
    Layer5Derivatives,
    Derivado,
)

_PLACEHOLDER_PERSISTENCE_STATE = "placeholder_not_persisted"


def apply_layer5(dm: DocumentMemory) -> DocumentMemory:
    """
    Gera derivados mínimos só para cumprir o contrato atual:

    - Cada derivado precisa de tipo e uri.
    - Tipos esperados:
      * imagem: thumbnail
      * video: frame_chave
      * audio: waveform
      * documento: preview
    - Mantém derivados como placeholders explícitos.
    - Não afirma persistência real enquanto não houver backend de storage.
    """
    # layer5 pode vir como dict (DocumentMemory v0.2.0), então sempre sobrescreve
    if dm.layer5 is None or not isinstance(dm.layer5, Layer5Derivatives):
        dm.layer5 = Layer5Derivatives()

    midia = dm.layer1.midia if dm.layer1 else None

    # limpa derivados para ser determinístico
    dm.layer5.imagens_derivadas = []
    dm.layer5.videos_derivados = []
    dm.layer5.audios_derivados = []
    dm.layer5.documentos_derivados = []

    # ---------------- IMAGEM ----------------
    if midia == MediaType.imagem:
        dm.layer5.imagens_derivadas.append(
            Derivado(tipo="thumbnail", uri="generated://thumbnail.jpg")
        )

    # ---------------- VÍDEO ----------------
    elif midia == MediaType.video:
        dm.layer5.videos_derivados.append(
            Derivado(tipo="frame_chave", uri="generated://frame.jpg")
        )

    # ---------------- ÁUDIO ----------------
    elif midia == MediaType.audio:
        dm.layer5.audios_derivados.append(
            Derivado(tipo="waveform", uri="generated://waveform.png")
        )

    # ---------------- DOCUMENTO ----------------
    elif midia == MediaType.documento:
        dm.layer5.documentos_derivados.append(
            Derivado(tipo="preview", uri="generated://preview.pdf")
        )

    dm.layer5.storage_uris = []
    dm.layer5.persistence_state = _PLACEHOLDER_PERSISTENCE_STATE

    return dm
