from pathlib import Path
from datetime import datetime
from hashlib import sha256
import pprint

from relluna.core.basic_pipeline import run_basic_pipeline
from relluna.core.document_memory import (
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    ArtefatoBruto,
    MediaType,
    OriginType,
)


def debug_dm(path: Path, midia: MediaType, origem: OriginType = OriginType.digital_nativo):
    with path.open("rb") as f:
        content = f.read()

    layer0 = Layer0Custodia(
        documentid=f"debug-{path.name}",
        contentfingerprint=sha256(content).hexdigest(),
        ingestiontimestamp=datetime.utcnow(),
        ingestionagent="debug-repl",
    )

    artefato = ArtefatoBruto(
        id=path.name,
        tipo="original",
        uri=str(path),
        metadados_nativos={},
    )

    layer1 = Layer1Artefatos(
        midia=midia,
        origem=origem,
        artefatos=[artefato],
    )

    dm = DocumentMemory(layer0=layer0, layer1=layer1)
    dm2 = run_basic_pipeline(dm)

    print("\n=== LAYER 0 ===")
    pprint.pp(dm2.layer0.model_dump(mode="python", exclude_none=False))

    print("\n=== LAYER 1 ===")
    pprint.pp(dm2.layer1.model_dump(mode="python", exclude_none=False))

    if dm2.layer2 is not None:
        print("\n=== LAYER 2 ===")
        pprint.pp(dm2.layer2.model_dump(mode="python", exclude_none=False))

    if dm2.layer3 is not None:
        print("\n=== LAYER 3 ===")
        pprint.pp(dm2.layer3.model_dump(mode="python", exclude_none=False))

    return dm2
