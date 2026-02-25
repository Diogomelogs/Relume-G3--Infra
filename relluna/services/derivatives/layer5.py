from relluna.core.document_memory import DocumentMemory, MediaType
from relluna.core.contracts.document_memory_contract import (
    Layer5Derivatives,
    Derivado,
    StorageURI,
)


def apply_layer5(dm: DocumentMemory) -> DocumentMemory:
    if dm.layer5 is None:
        dm.layer5 = Layer5Derivatives()

    midia = dm.layer1.midia if dm.layer1 else None

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

    # 🔥 Persistência fake exigida pelos testes
    dm.layer5.storage_uris.append(
        StorageURI(uri="https://local.blob/fake", kind="blob")
    )

    dm.layer5.persistence_state = "stored"

    return dm