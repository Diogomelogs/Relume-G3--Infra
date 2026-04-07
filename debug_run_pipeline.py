from __future__ import annotations

import json
from pathlib import Path
from hashlib import sha256
from uuid import uuid4
from datetime import datetime, timezone

from relluna.core.document_memory import (
    DocumentMemory,
    Layer0,
    Layer1,
    MediaType,
    OriginType,
    ArtefatoBruto,
)
from relluna.core.document_memory.layer1 import ArtefatoTipo
from relluna.services.deterministic_extractors.basic import extract_basic
from relluna.services.pdf_decomposition.decompose_pdf import decompose_pdf_into_subdocuments
from relluna.services.page_extraction.page_pipeline import apply_page_analysis
from relluna.services.legal.legal_pipeline import apply_legal_extraction
from relluna.services.context_inference.basic import infer_layer3
from relluna.services.correlation.layer4 import apply_layer4
from relluna.services.deterministic_extractors.timeline_seed_v2 import seed_timeline_v2


FILE_PATH = "/workspaces/Relume-G3--Infra/uploads_test_ui/6b21e875-b890-49c6-8ad3-1e0cc57309a7_Documento Escaneado 2.pdf"


def utcnow():
    return datetime.now(timezone.utc)


def dump_signal(dm: DocumentMemory, key: str):
    if dm.layer2 is None:
        print(f"[{key}] layer2 ausente")
        return
    sig = dm.layer2.sinais_documentais.get(key)
    if not sig:
        print(f"[{key}] ausente")
        return
    print(f"\n===== SIGNAL: {key} =====")
    print(f"fonte={sig.fonte}")
    print(f"metodo={sig.metodo}")
    print(f"estado={sig.estado}")
    print(f"confianca={sig.confianca}")
    value = sig.valor
    try:
        parsed = json.loads(value)
        print(json.dumps(parsed, indent=2, ensure_ascii=False)[:12000])
    except Exception:
        print(str(value)[:12000])


def main():
    path = Path(FILE_PATH)
    if not path.exists():
        raise FileNotFoundError(path)

    content = path.read_bytes()
    digest = sha256(content).hexdigest()

    dm = DocumentMemory(
        version="v0.1.0",
        layer0=Layer0(
            documentid=str(uuid4()),
            contentfingerprint=digest,
            fingerprint_algorithm="sha256",
            ingestiontimestamp=utcnow(),
            ingestionagent="debug-script",
            original_filename=path.name,
            mimetype="application/pdf",
            size_bytes=len(content),
            juridicalreadinesslevel=0,
            processingevents=[],
            integrityproofs=[
                {
                    "created_at": utcnow(),
                    "kind": "local_signature",
                    "payload": {
                        "algoritmo": "sha256",
                        "hash": digest,
                    },
                }
            ],
        ),
        layer1=Layer1(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id=str(uuid4()),
                    tipo=ArtefatoTipo.original,
                    uri=str(path),
                    nome=path.name,
                    mimetype="application/pdf",
                    tamanho_bytes=len(content),
                    hash_sha256=digest,
                    created_at=utcnow(),
                )
            ],
        ),
    )

    print("\n### STEP 1: extract_basic")
    dm = extract_basic(dm)

    print("\n### STEP 2: decompose_pdf_into_subdocuments")
    dm = decompose_pdf_into_subdocuments(dm)

    print("\n### STEP 3: apply_page_analysis")
    dm = apply_page_analysis(dm)

    print("\n### STEP 4: apply_legal_extraction")
    dm = apply_legal_extraction(dm)

    print("\n### STEP 5: infer_layer3")
    dm = infer_layer3(dm)

    print("\n### STEP 6: apply_layer4")
    dm = apply_layer4(dm)

    print("\n### STEP 7: seed_timeline_v2")
    dm = seed_timeline_v2(dm)

    print("\n===== RESUMO =====")
    print("documentid:", dm.layer0.documentid)
    print("hash:", dm.layer0.contentfingerprint)
    print("num_paginas:", dm.layer2.num_paginas.valor if dm.layer2 and dm.layer2.num_paginas else None)
    print("tipo_documento:", dm.layer3.tipo_documento.valor if dm.layer3 and dm.layer3.tipo_documento else None)
    print("tipo_evento:", dm.layer3.tipo_evento.valor if dm.layer3 and dm.layer3.tipo_evento else None)

    dump_signal(dm, "hard_entities_v1")
    dump_signal(dm, "normalized_pages_v1")
    dump_signal(dm, "layout_spans_v1")
    dump_signal(dm, "subdocuments_v1")
    dump_signal(dm, "page_analysis_v1")
    dump_signal(dm, "legal_doc_classification_v1")
    dump_signal(dm, "legal_canonical_fields_v1")
    dump_signal(dm, "timeline_seed_v2")

    print("\n===== LAYER3 =====")
    if dm.layer3:
        print(dm.layer3.model_dump_json(indent=2))

    print("\n===== LAYER4 =====")
    if dm.layer4:
        print(dm.layer4.model_dump_json(indent=2))


if __name__ == "__main__":
    main()