# tests/test_document_memory_canonical_pdf.py

import json
from pathlib import Path

from relluna.core.document_memory import DocumentMemory_v0_2_0

GOLDEN_PDF = Path(__file__).parent / "data" / "golden" / "GOLDEN-PDF-DIGITAL.json"

def test_golden_pdf_v020_eh_canonico():
    raw = GOLDEN_PDF.read_text(encoding="utf-8")
    data = json.loads(raw)

    dm = DocumentMemory_v0_2_0.model_validate(data)

    # sanity checks mínimos
    assert dm.version == "v0.2.0"
    assert dm.layer0 is not None
    assert dm.layer1 is not None
    assert dm.layer2 is not None
