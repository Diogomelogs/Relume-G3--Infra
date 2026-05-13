from relluna.core.document_memory import (
    Layer0Custodia,
    Layer1Artefatos,
    Layer2Evidence,
    Layer3Evidence,
    Layer4SemanticNormalization,
    Layer6Optimization,
    ArtefatoBruto,
    MediaType,
    OriginType,
)

from datetime import datetime, UTC
import uuid


def run():
    print("\n=== Instanciando Layer0 ===")
    l0 = Layer0Custodia(
        documentid=str(uuid.uuid4()),
        contentfingerprint="a" * 64,
        ingestiontimestamp=datetime.now(UTC),
        ingestionagent="debug",
    )
    print("Layer0 OK")

    print("\n=== Instanciando Layer1 ===")
    l1 = Layer1Artefatos(
        midia=MediaType.imagem,
        origem=OriginType.digital_nativo,
        artefatos=[
            ArtefatoBruto(
                id="original",
                tipo="original",
                uri="/tmp/file.jpg"
            )
        ],
    )
    print("Layer1 OK")

    print("\n=== Instanciando Layer2 ===")
    l2 = Layer2Evidence()
    print("Layer2 OK")

    print("\n=== Instanciando Layer3 ===")
    l3 = Layer3Evidence()
    print("Layer3 OK")

    print("\n=== Instanciando Layer4 ===")
    l4 = Layer4SemanticNormalization()
    print("Layer4 OK")

    print("\n=== Instanciando Layer6 ===")
    l6 = Layer6Optimization()
    print("Layer6 OK")

    print("\n✔ Todas as Layers instanciadas com sucesso.")


if __name__ == "__main__":
    run()