from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from relluna.core.document_memory import (
    ArtefatoBruto,
    DocumentMemory,
    Layer0,
    Layer1,
    MediaType,
    OriginType,
)
from relluna.core.document_memory.layer1 import ArtefatoTipo
from relluna.services.deterministic_extractors.basic import extract_basic
from relluna.services.pdf_decomposition.decompose_pdf import decompose_pdf_into_subdocuments
from relluna.services.page_extraction.page_pipeline import apply_page_analysis
from relluna.services.legal.legal_pipeline import apply_legal_extraction
from relluna.services.entities.entities_canonical_v1 import apply_entities_canonical_v1
from relluna.services.deterministic_extractors.timeline_seed_v2 import seed_timeline_v2
from relluna.services.context_inference.basic import infer_layer3
from relluna.services.correlation.layer4 import apply_layer4
from relluna.services.derivatives.layer5 import apply_layer5


def load_json_signal(dm: DocumentMemory, key: str) -> Any:
    if dm.layer2 is None:
        return None
    sig = dm.layer2.sinais_documentais.get(key)
    if not sig or not getattr(sig, "valor", None):
        return None
    try:
        return json.loads(sig.valor)
    except Exception:
        return sig.valor


def short(value: Any, limit: int = 1600) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... [TRUNCADO]"


def summarize_page_evidence(page_evidence: Any) -> list[dict]:
    if not isinstance(page_evidence, list):
        return []

    summary: list[dict] = []
    for item in page_evidence:
        if not isinstance(item, dict):
            continue

        people = item.get("people") or {}
        clinical = item.get("clinical_entities") or {}
        page_taxonomy = item.get("page_taxonomy") or {}

        summary.append(
            {
                "page": item.get("page"),
                "subdoc_id": item.get("subdoc_id"),
                "page_taxonomy": page_taxonomy.get("value"),
                "patient": people.get("patient_name"),
                "provider": people.get("provider_name"),
                "mother": people.get("mother_name"),
                "cids": clinical.get("cids"),
                "service": clinical.get("service"),
                "specialty": clinical.get("specialty"),
            }
        )
    return summary


def summarize_subdocuments(subdocs: Any) -> list[dict]:
    if not isinstance(subdocs, list):
        return []

    out: list[dict] = []
    for item in subdocs:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "subdoc_id": item.get("subdoc_id"),
                "doc_type": item.get("doc_type"),
                "pages": item.get("pages"),
            }
        )
    return out


def summarize_probatory_events(dm: DocumentMemory) -> list[dict]:
    out: list[dict] = []
    if not dm.layer3:
        return out

    for event in getattr(dm.layer3, "eventos_probatorios", None) or []:
        out.append(
            {
                "event_id": getattr(event, "event_id", None),
                "event_type": getattr(event, "event_type", None),
                "date_iso": getattr(event, "date_iso", None),
                "title": getattr(event, "title", None),
                "confidence": getattr(event, "confidence", None)
                if getattr(event, "confidence", None) is not None
                else getattr(event, "confianca", None),
                "review_state": getattr(event, "review_state", None),
            }
        )
    return out


def dump_stage(name: str, dm: DocumentMemory) -> None:
    print("\n" + "=" * 80)
    print(f"STAGE: {name}")
    print("=" * 80)

    tipo_doc = None
    if dm.layer3 and getattr(dm.layer3, "tipo_documento", None):
        tipo_doc = dm.layer3.tipo_documento.valor
    print(f"layer3.tipo_documento: {tipo_doc}")

    canonical = load_json_signal(dm, "entities_canonical_v1")
    timeline = load_json_signal(dm, "timeline_seed_v2")
    page_evidence = load_json_signal(dm, "page_evidence_v1")
    subdocs = load_json_signal(dm, "subdocuments_v1")

    if subdocs is not None:
        print("\nsubdocuments_v1 summary:")
        print(short(summarize_subdocuments(subdocs), limit=2500))

    if page_evidence is not None:
        print("\npage_evidence_v1 pages summary:")
        print(short(summarize_page_evidence(page_evidence), limit=2500))

        print("\npage_evidence_v1[0] summary:")
        first = page_evidence[0] if isinstance(page_evidence, list) and page_evidence else page_evidence
        print(short(first, limit=2500))

    if canonical is not None:
        print("\nentities_canonical_v1:")
        print(short(canonical, limit=3000))

    if timeline is not None:
        print("\ntimeline_seed_v2:")
        print(short(timeline, limit=3000))

    probatory = summarize_probatory_events(dm)
    if probatory:
        print("\nlayer3.eventos_probatorios summary:")
        print(short(probatory, limit=2500))

    if dm.layer5 and getattr(dm.layer5, "read_models", None):
        print("\nlayer5.read_models.timeline_v1:")
        print(short(dm.layer5.read_models.get("timeline_v1"), limit=3000))

        print("\nlayer5.read_models.entity_summary_v1:")
        print(short(dm.layer5.read_models.get("entity_summary_v1"), limit=2200))


def build_dm_from_file(path: Path) -> DocumentMemory:
    content = path.read_bytes()
    real_hash = hashlib.sha256(content).hexdigest()

    layer0 = Layer0(
        documentid="debug-doc",
        contentfingerprint=real_hash,
        fingerprint_algorithm="sha256",
        ingestionagent="debug",
        original_filename=path.name,
        mimetype="application/pdf",
        size_bytes=len(content),
    )

    layer1 = Layer1(
        midia=MediaType.documento,
        origem=OriginType.digital_nativo,
        artefatos=[
            ArtefatoBruto(
                id="debug-doc",
                tipo=ArtefatoTipo.original,
                uri=str(path),
                nome=path.name,
                mimetype="application/pdf",
                tamanho_bytes=len(content),
            )
        ],
    )

    return DocumentMemory(version="v0.2.0", layer0=layer0, layer1=layer1)


def resolve_pdf_path(user_path: Optional[str]) -> Path:
    if user_path:
        path = Path(user_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")
        return path

    candidates = list(Path(".uploads").glob("*.pdf"))
    if not candidates:
        raise FileNotFoundError(
            "Nenhum PDF encontrado em .uploads. Passe o caminho com --pdf."
        )

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Debug step-by-step do pipeline de documentos PDF."
    )
    parser.add_argument(
        "--pdf",
        type=str,
        default=None,
        help="Caminho do PDF. Se omitido, usa o PDF mais recente em .uploads/",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdf_path = resolve_pdf_path(args.pdf)

    print(f"Usando arquivo: {pdf_path}")
    dm = build_dm_from_file(pdf_path)

    dump_stage("initial", dm)

    dm = extract_basic(dm)
    dump_stage("extract_basic", dm)

    dm = decompose_pdf_into_subdocuments(dm)
    dump_stage("decompose_pdf_into_subdocuments", dm)

    dm = apply_page_analysis(dm)
    dump_stage("apply_page_analysis", dm)

    dm = apply_legal_extraction(dm)
    dump_stage("apply_legal_extraction", dm)

    dm = apply_entities_canonical_v1(dm)
    dump_stage("apply_entities_canonical_v1", dm)

    dm = seed_timeline_v2(dm)
    dump_stage("timeline_seed_v2", dm)

    dm = infer_layer3(dm)
    dump_stage("infer_layer3", dm)

    dm = apply_layer4(dm)
    dump_stage("apply_layer4", dm)

    dm = apply_layer5(dm)
    dump_stage("apply_layer5", dm)


if __name__ == "__main__":
    main()