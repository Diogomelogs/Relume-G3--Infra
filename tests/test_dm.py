from pathlib import Path
from hashlib import sha256
from datetime import datetime, UTC

from relluna.core.basic_pipeline import run_basic_pipeline
from relluna.core.document_memory import (
    DocumentMemory,
    MediaType,
    OriginType,
    ArtefatoBruto,
    Layer0Custodia as Layer0,
    Layer1,
)

# Caminho da imagem
p = Path("uploads_test_ui/6fd749b8-e23e-42b2-b9f0-17e865423edb_2B1605D6-1075-4537-AD00-41499B0A7880.JPG")

content = p.read_bytes()
digest = sha256(content).hexdigest()
now = datetime.now(UTC)

# Criação do DocumentMemory
dm = DocumentMemory(
    layer0=Layer0(
        documentid="dm-test",
        contentfingerprint=digest,
        ingestiontimestamp=now,
        ingestionagent="dm-test",
        integrityproofs=[{"algoritmo": "sha256", "hash": digest}],
        juridicalreadinesslevel=0,
        processingevents=[],
    ),
    layer1=Layer1(
        midia=MediaType.imagem,
        origem=OriginType.digitalizado,
        artefatos=[
            ArtefatoBruto(
                id="dm-test",
                tipo="original",
                uri=str(p),
                nome=p.name,
                mimetype="image/jpeg",
                tamanho_bytes=len(content),
                created_at=now,
            )
        ],
    ),
)

# Executa pipeline
dm = run_basic_pipeline(dm)

print("✅ DM PROCESSADO!")

# Acesso seguro ao OCR
ocr_obj = getattr(dm.layer2, "texto_ocr_literal", None)
ocr_val = getattr(ocr_obj, "valor", None) or ""

print("OCR estado:", getattr(ocr_obj, "estado", None))
print("OCR valor preview:", repr(ocr_val[:100]))
print("OCR len:", len(ocr_val))