from __future__ import annotations

import time
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


def build_dm(path: str) -> DocumentMemory:
    p = Path(path)
    content = p.read_bytes()
    digest = sha256(content).hexdigest()

    return DocumentMemory(
        version="v0.1.0",
        layer0=Layer0(
            documentid=str(uuid4()),
            contentfingerprint=digest,
            fingerprint_algorithm="sha256",
            ingestiontimestamp=utcnow(),
            ingestionagent="profile-script",
            original_filename=p.name,
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
                    uri=str(p),
                    nome=p.name,
                    mimetype="application/pdf",
                    tamanho_bytes=len(content),
                    hash_sha256=digest,
                    created_at=utcnow(),
                )
            ],
        ),
    )


def step(name, fn, dm):
    t0 = time.perf_counter()
    out = fn(dm)
    dt = time.perf_counter() - t0
    print(f"{name:<30} {dt:>8.2f}s")
    return out, dt


def main():
    dm = build_dm(FILE_PATH)

    totals = []

    dm, dt = step("extract_basic", extract_basic, dm)
    totals.append(("extract_basic", dt))

    dm, dt = step("decompose_pdf_into_subdocs", decompose_pdf_into_subdocuments, dm)
    totals.append(("decompose_pdf_into_subdocs", dt))

    dm, dt = step("apply_page_analysis", apply_page_analysis, dm)
    totals.append(("apply_page_analysis", dt))

    dm, dt = step("apply_legal_extraction", apply_legal_extraction, dm)
    totals.append(("apply_legal_extraction", dt))

    dm, dt = step("infer_layer3", infer_layer3, dm)
    totals.append(("infer_layer3", dt))

    dm, dt = step("apply_layer4", apply_layer4, dm)
    totals.append(("apply_layer4", dt))

    dm, dt = step("seed_timeline_v2", seed_timeline_v2, dm)
    totals.append(("seed_timeline_v2", dt))

    total = sum(v for _, v in totals)
    print("\nTOTAL")
    print(f"{total:.2f}s")


if __name__ == "__main__":
    main()