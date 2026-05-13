from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.types_basic import ProvenancedString


def _prov_json(payload: Any, fonte: str, metodo: str) -> ProvenancedString:
    return ProvenancedString(
        valor=json.dumps(payload, ensure_ascii=False),
        fonte=fonte,
        metodo=metodo,
        estado="confirmado",
        confianca=1.0,
        lastro=[],
    )


def extract_pdf_layout_spans(dm: DocumentMemory, max_pages: int = 300) -> DocumentMemory:
    """
    Extrai spans de texto + bbox para PDF com texto nativo.
    Persiste em layer2.sinais_documentais["layout_spans_v1"] como JSON string.
    """
    if dm.layer1 is None or not dm.layer1.artefatos:
        return dm
    if dm.layer2 is None:
        return dm

    artef = dm.layer1.artefatos[0]
    if not artef.mimetype or "pdf" not in (artef.mimetype.lower()):
        return dm
    if not artef.uri:
        return dm

    try:
        doc = fitz.open(artef.uri)
    except Exception:
        return dm

    spans: List[Dict[str, Any]] = []
    n_pages = min(doc.page_count, max_pages)

    for i in range(n_pages):
        page = doc.load_page(i)
        d = page.get_text("dict")
        for b in d.get("blocks", []):
            for line in b.get("lines", []):
                for sp in line.get("spans", []):
                    txt = (sp.get("text") or "").strip()
                    if not txt:
                        continue
                    bbox = sp.get("bbox")
                    if not bbox or len(bbox) != 4:
                        continue
                    spans.append(
                        {
                            "page": i + 1,
                            "text": txt,
                            "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])],
                        }
                    )

    doc.close()

    # se nada veio, não grava
    if not spans:
        return dm

    dm.layer2.sinais_documentais["layout_spans_v1"] = _prov_json(
        spans,
        fonte="deterministic_extractors.pdf_layout",
        metodo="pymupdf.get_text(dict).spans",
    )
    return dm