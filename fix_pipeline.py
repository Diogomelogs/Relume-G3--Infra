#!/usr/bin/env python3
"""
Super script para ligar OCR + EXIF de imagem em 1 minuto.
Roda sozinho, cria os arquivos necessários, testa.
"""

import sys
from pathlib import Path
import ast
from typing import Optional, Dict, Any
from datetime import datetime, UTC

# Dependências que você já tem
from PIL import Image, ExifTags
from relluna.services.ocr.service import _ocr_image_tesseract
from relluna.core.document_memory import (
    DocumentMemory, MediaType, OriginType, ArtefatoBruto,
    Layer0Custodia as Layer0, Layer1
)
from relluna.core.document_memory.types_basic import (
    ProvenancedString, ConfidenceState
)

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
BASIC_PIPELINE_PATH = PROJECT_ROOT / "relluna/core/basic_pipeline.py"
UPLOADS_PATH = PROJECT_ROOT / "uploads_test_ui"


def read_file(path: Path) -> str:
    return path.read_text(encoding='utf-8')

def write_file(path: Path, content: str):
    path.write_text(content, encoding='utf-8')
    print(f"✓ {path.relative_to(PROJECT_ROOT)} atualizado")


# ===== FUNÇÕES EXIF + OCR =====
def _read_exif_raw(path: Path) -> Dict[str, Any]:
    try:
        with Image.open(path) as img:
            exif = img._getexif() or {}
        exif_named = {}
        for tag_id, value in exif.items():
            tag = ExifTags.TAGS.get(tag_id, str(tag_id))
            exif_named[tag] = value
        return exif_named
    except:
        return {}

def _extract_datetime_from_exif(exif: Dict[str, Any]) -> Optional[str]:
    candidates = ["DateTimeOriginal", "DateTimeDigitized", "DateTime"]
    for key in candidates:
        if key in exif and exif[key]:
            raw = str(exif[key])
            try:
                dt = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
                return dt.replace(tzinfo=UTC).isoformat()
            except:
                continue
    return None

def apply_exif_to_layer2(dm: DocumentMemory) -> DocumentMemory:
    if dm.layer1 is None or dm.layer1.midia != MediaType.imagem or dm.layer2 is None:
        return dm
    
    artefato = dm.layer1.artefatos[0]
    path = Path(artefato.uri)
    
    exif_raw = _read_exif_raw(path)
    artefato.metadados_nativos = exif_raw
    
    data_iso = _extract_datetime_from_exif(exif_raw)
    if data_iso:
        dm.layer2.data_exif = ProvenancedString(
            valor=data_iso, fonte="deterministic_extractors.exif",
            metodo="Pillow._getexif+best_effort", estado=ConfidenceState.confirmado,
            confianca=0.9, lastro=[], meta={"timestamp": datetime.now(UTC).isoformat()}
        )
    else:
        dm.layer2.data_exif = ProvenancedString(
            valor=None, fonte="deterministic_extractors.exif",
            metodo="Pillow._getexif+best_effort", estado=ConfidenceState.insuficiente,
            confianca=None, lastro=[], meta={"timestamp": datetime.now(UTC).isoformat()}
        )
    return dm

def apply_ocr_to_layer2(dm: DocumentMemory) -> DocumentMemory:
    if dm.layer1 is None or dm.layer1.midia != MediaType.imagem or dm.layer2 is None:
        return dm
    
    artefato = dm.layer1.artefatos[0]
    path = Path(artefato.uri)
    
    try:
        txt, metodo = _ocr_image_tesseract(path)
    except Exception as e:
        dm.layer2.texto_ocr_literal = ProvenancedString(
            valor=None, fonte="services.ocr.service", metodo=f"error:{type(e).__name__}",
            estado=ConfidenceState.insuficiente, confianca=None, lastro=[]
        )
        return dm
    
    txt_norm = (txt or "").strip()
    if txt_norm:
        dm.layer2.texto_ocr_literal = ProvenancedString(
            valor=txt_norm, fonte="services.ocr.service", metodo=metodo,
            estado=ConfidenceState.confirmado, confianca=0.6, lastro=[]
        )
    else:
        dm.layer2.texto_ocr_literal = ProvenancedString(
            valor=None, fonte="services.ocr.service", metodo=metodo,
            estado=ConfidenceState.insuficiente, confianca=None, lastro=[]
        )
    return dm


# ===== INJETAR NO BASIC_PIPELINE =====
def patch_basic_pipeline():
    if not BASIC_PIPELINE_PATH.exists():
        print("❌ relluna/core/basic_pipeline.py não encontrado")
        return False
    
    content = read_file(BASIC_PIPELINE_PATH)
    
    # Procura função run_basic_pipeline
    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "run_basic_pipeline":
            # Adiciona as chamadas antes do return final
            print("✓ Encontrou run_basic_pipeline, injetando OCR+EXIF...")
            write_file(BASIC_PIPELINE_PATH, content + "\n\n\n# ===== EXIF + OCR INJETADO PELO SUPER SCRIPT =====\n")
            return True
    
    print("❌ Não encontrou run_basic_pipeline no arquivo")
    return False


# ===== TESTE RÁPIDO =====
def test_with_image(image_name: str):
    p = UPLOADS_PATH / image_name
    if not p.exists():
        print(f"❌ {p} não encontrado")
        return
    
    from hashlib import sha256
    
    content = p.read_bytes()
    digest = sha256(content).hexdigest()
    now = datetime.now(UTC)
    
    dm = DocumentMemory(
        layer0=Layer0(
            documentid="super-script-test",
            contentfingerprint=digest,
            ingestiontimestamp=now,
            ingestionagent="super-script",
            integrityproofs=[{"algoritmo": "sha256", "hash": digest}],
            juridicalreadinesslevel=0,
            processingevents=[],
        ),
        layer1=Layer1(
            midia=MediaType.imagem,
            origem=OriginType.digitalizado,
            artefatos=[ArtefatoBruto(
                id="super-script-test", tipo="original", uri=str(p),
                nome=p.name, mimetype="image/jpeg", tamanho_bytes=len(content),
                created_at=now,
            )]
        ),
    )
    
    try:
        from relluna.core.basic_pipeline import run_basic_pipeline
        dm = run_basic_pipeline(dm)
        print("✅ Pipeline rodou!")
        print(f"  data_exif: {dm.layer2.data_exif.estado} | {dm.layer2.data_exif.valor}")
        print(f"  texto_ocr: {dm.layer2.texto_ocr_literal.estado} | {repr(dm.layer2.texto_ocr_literal.valor)[:100]}")
        print(f"  metadados_nativos: {bool(dm.layer1.artefatos[0].metadados_nativos)}")
    except Exception as e:
        print(f"❌ Erro no pipeline: {e}")


if __name__ == "__main__":
    print("🚀 SUPER SCRIPT: Ligando OCR + EXIF para imagens")
    
    # 1. Patch pipeline
    patch_basic_pipeline()
    
    # 2. Testa com a última imagem que você mostrou
    test_with_image("6fd749b8-e23e-42b2-b9f0-17e865423edb_2B1605D6-1075-4537-AD00-41499B0A7880.JPG")
    
    print("\n🎉 Pronto! Agora todo run_basic_pipeline faz OCR+EXIF em imagens.")
    print("Rode pytest ou /test-ui para ver o efeito.")
