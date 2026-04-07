from pathlib import Path
from datetime import datetime, UTC
import uuid
import hashlib

from relluna.core.document_memory import (
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    ArtefatoBruto,
    MediaType,
    OriginType,
)
from relluna.core.basic_pipeline import run_basic_pipeline


# 🔹 Ajuste aqui para qualquer imagem real
FILE = "/workspaces/Relume-G3--Infra/uploads/8810c947ede090da1c3b8b882a013dc9132e88528461fdcd53f57e6ce62c86b5_IMG_0770.HEIC"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run():
    path = Path(FILE)

    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {FILE}")

    with open(path, "rb") as f:
        file_bytes = f.read()

    # -----------------------------
    # Criar DocumentMemory manual
    # -----------------------------
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid=str(uuid.uuid4()),
            contentfingerprint=sha256_bytes(file_bytes),
            ingestiontimestamp=datetime.now(UTC),
            ingestionagent="debug_real_image",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.imagem,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="original",
                    tipo="original",
                    uri=str(path),
                )
            ],
        ),
    )

    # -----------------------------
    # Executar pipeline determinístico
    # -----------------------------
    dm = run_basic_pipeline(dm)

    # -----------------------------
    # Imprimir resultado completo
    # -----------------------------
    print("\n==============================")
    print("VERSION")
    print("==============================")
    print(dm.version)

    print("\n==============================")
    print("LAYER 0 – CUSTÓDIA")
    print("==============================")
    print(dm.layer0.model_dump())

    print("\n==============================")
    print("LAYER 1 – ARTEFATOS")
    print("==============================")
    print(dm.layer1.model_dump())

    print("\n==============================")
    print("LAYER 2 – EVIDÊNCIA DETERMINÍSTICA")
    print("==============================")
    print(dm.layer2.model_dump() if dm.layer2 else None)

    print("\n==============================")
    print("LAYER 3 – INFERÊNCIA RASTREÁVEL")
    print("==============================")
    print(dm.layer3.model_dump() if dm.layer3 else None)


if __name__ == "__main__":
    run()