from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from time import perf_counter
from typing import List, Dict, Any, Literal

from pypdf import PdfReader

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.types_basic import ProvenancedString
from relluna.services.observability import append_processing_event, elapsed_ms
from relluna.services.page_extraction.page_normalizer import normalize_pdf_pages
from relluna.services.page_extraction.page_ocr import OCRPage, ocr_pages, OCR_PAGE_TIMEOUT_SECONDS
from relluna.services.page_extraction.page_strategy import classify_pdf_page_strategies
from relluna.services.page_extraction.page_taxonomy import classify_page_subtype

FONTE = "services.pdf_decomposition.decompose_pdf_v5"

ExtractionStrategy = Literal["native", "hybrid", "ocr"]


def _make_signal(dm: DocumentMemory, key: str, value: Any) -> DocumentMemory:
    if dm.layer2 is None:
        return dm

    dm.layer2.sinais_documentais[key] = ProvenancedString(
        valor=json.dumps(value, ensure_ascii=False),
        fonte=FONTE,
        metodo=key,
        estado="confirmado",
        confianca=1.0,
    )
    return dm


def _safe_text(value: Any) -> str:
    return (value or "").strip()


def _extract_native_pdf_pages(path: Path) -> List[Dict[str, Any]]:
    pages: List[Dict[str, Any]] = []

    try:
        reader = PdfReader(str(path))
        for i, page in enumerate(reader.pages):
            text = _safe_text(page.extract_text())
            image_count = _count_pdf_page_images(page)
            pages.append(
                {
                    "page": i + 1,
                    "text": text,
                    "source": "native_pdf",
                    "has_images": image_count > 0,
                    "image_count": image_count,
                }
            )
    except Exception:
        return []

    return pages


def _count_pdf_page_images(page: Any) -> int:
    try:
        resources = page.get("/Resources") or {}
        if hasattr(resources, "get_object"):
            resources = resources.get_object()
        xobjects = resources.get("/XObject") if hasattr(resources, "get") else None
        if xobjects is None:
            return 0
        if hasattr(xobjects, "get_object"):
            xobjects = xobjects.get_object()

        count = 0
        for value in xobjects.values():
            obj = value.get_object() if hasattr(value, "get_object") else value
            if getattr(obj, "get", lambda *_: None)("/Subtype") == "/Image":
                count += 1
        return count
    except Exception:
        return 0


def _page_quality_score(text: str) -> float:
    text = _safe_text(text)
    if not text:
        return 0.0

    alpha_chars = sum(1 for c in text if c.isalpha())
    digit_chars = sum(1 for c in text if c.isdigit())
    spaces = sum(1 for c in text if c.isspace())
    weird_chars = len(text) - alpha_chars - digit_chars - spaces

    score = 0.0
    score += min(len(text) / 300.0, 4.0)
    score += min(alpha_chars / max(len(text), 1), 1.0) * 3.0
    score += min(digit_chars / max(len(text), 1), 1.0) * 0.5
    score -= min(weird_chars / max(len(text), 1), 1.0) * 2.0

    lowered = text.lower()
    for hint in [
        "nome", "data", "cpf", "cnpj", "crm", "paciente", "hospital",
        "benefício", "beneficio", "receituario", "receituário",
        "assinatura", "endereço", "endereco",
    ]:
        if hint in lowered:
            score += 0.5

    return score


def _decide_extraction_strategy(native_pages: List[Dict[str, Any]]) -> ExtractionStrategy:
    if not native_pages:
        return "ocr"

    texts = [_safe_text(p.get("text")) for p in native_pages]
    num_pages = len(texts)

    total_chars = sum(len(t) for t in texts)
    empty_pages = sum(1 for t in texts if len(t) < 20)
    good_pages = sum(1 for t in texts if _page_quality_score(t) >= 2.5)

    if total_chars < 50:
        return "ocr"

    if good_pages == num_pages and empty_pages == 0:
        return "native"

    if good_pages >= max(1, int(num_pages * 0.5)):
        return "hybrid"

    return "ocr"


def _reconstruct_full_text(pages: List[Dict[str, Any]]) -> str:
    return "\n".join(
        _safe_text(p.get("text"))
        for p in pages
        if _safe_text(p.get("text"))
    ).strip()


def _normalize_page_images_to_dicts(page_images: List[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    for item in page_images:
        if is_dataclass(item):
            payload = asdict(item)
        elif isinstance(item, dict):
            payload = dict(item)
        else:
            payload = {
                "page": getattr(item, "page"),
                "image_path": getattr(item, "image_path"),
                "width": getattr(item, "width", None),
                "height": getattr(item, "height", None),
                "rotation_applied": getattr(item, "rotation_applied", None),
                "source_pdf_rotation": getattr(item, "source_pdf_rotation", None),
                "orientation_score": getattr(item, "orientation_score", None),
                "warnings": getattr(item, "warnings", []),
            }
        out.append(payload)

    return out


def _collect_page_warnings(page_images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    for item in page_images:
        for warning in item.get("warnings") or []:
            if isinstance(warning, dict):
                warnings.append(warning)
    return warnings


def _collect_ocr_warnings(ocr_result: List[Any]) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    for page in ocr_result:
        for warning in getattr(page, "warnings", []) or []:
            if isinstance(warning, dict):
                warnings.append({key: value for key, value in warning.items() if value is not None})
    return warnings


def _degraded_mode_for_warning(warning: Dict[str, Any]) -> str | None:
    code = str(warning.get("code") or warning.get("warning_code") or "")
    if code.startswith("ocr_orientation"):
        return "orientation_degraded"
    if code.startswith("ocr_page"):
        return "ocr_page_degraded"
    return None


def _append_normalization_events(
    dm: DocumentMemory,
    normalized_pages_out: List[Dict[str, Any]],
    *,
    duration_ms: float,
) -> None:
    for item in normalized_pages_out:
        page_no = int(item.get("page") or 0)
        warnings = [w for w in item.get("warnings") or [] if isinstance(w, dict)]
        if not warnings:
            append_processing_event(
                dm,
                etapa="page_normalization",
                engine="services.page_extraction.page_normalizer",
                detalhes={
                    "duration_ms": duration_ms,
                    "page_index": page_no,
                    "rotation_applied": item.get("rotation_applied"),
                    "source_pdf_rotation": item.get("source_pdf_rotation"),
                },
                page_index=page_no,
            )
            continue

        for warning in warnings:
            append_processing_event(
                dm,
                etapa="page_normalization",
                engine="services.page_extraction.page_normalizer",
                status="warning",
                detalhes={**warning, "duration_ms": duration_ms},
                page_index=page_no,
                warning_code=warning.get("code"),
                degraded_mode=_degraded_mode_for_warning(warning),
            )


def _append_ocr_events(
    dm: DocumentMemory,
    ocr_result: List[OCRPage],
    page_strategy_by_page: Dict[int, Dict[str, Any]],
    *,
    duration_ms: float,
) -> None:
    for page in ocr_result:
        page_no = int(page.page)
        strategy = page_strategy_by_page.get(page_no, {}).get("strategy", "ocr_heavy")
        warnings = [w for w in getattr(page, "warnings", []) or [] if isinstance(w, dict)]

        if strategy in {"native_text", "image_only"}:
            append_processing_event(
                dm,
                etapa="page_ocr",
                engine="services.page_extraction.page_ocr",
                status="warning" if strategy == "image_only" else "success",
                detalhes={
                    "duration_ms": duration_ms,
                    "page_index": page_no,
                    "strategy": strategy,
                    "skipped": True,
                    "reason": "page_strategy_skipped_heavy_ocr",
                    "warning_code": "ocr_skipped_image_only" if strategy == "image_only" else None,
                    "fallback": {"from": "ocr", "to": strategy},
                    "degraded_mode": "image_only" if strategy == "image_only" else None,
                },
                page_index=page_no,
                warning_code="ocr_skipped_image_only" if strategy == "image_only" else None,
                fallback={"from": "ocr", "to": strategy},
                degraded_mode="image_only" if strategy == "image_only" else None,
            )
            continue

        if not warnings:
            append_processing_event(
                dm,
                etapa="page_ocr",
                engine="services.page_extraction.page_ocr",
                detalhes={
                    "duration_ms": duration_ms,
                    "page_index": page_no,
                    "strategy": strategy,
                    "span_count": len(page.spans or []),
                    "text_length": len(page.text or ""),
                },
                page_index=page_no,
            )
            continue

        for warning in warnings:
            append_processing_event(
                dm,
                etapa="page_ocr",
                engine="services.page_extraction.page_ocr",
                status="warning",
                detalhes={**warning, "duration_ms": duration_ms, "strategy": strategy},
                page_index=page_no,
                warning_code=warning.get("code"),
                degraded_mode=_degraded_mode_for_warning(warning),
            )


def _is_ocr_timeout_exception(exc: Exception) -> bool:
    return "tesseract" in str(exc).lower() and "timeout" in str(exc).lower()


def _build_degraded_ocr_result(
    normalized_pages_out: List[Dict[str, Any]],
    exc: Exception,
) -> List[OCRPage]:
    cause_message = str(exc) or exc.__class__.__name__
    pages: List[OCRPage] = []

    for item in normalized_pages_out:
        page_no = int(item.get("page") or 0)
        pages.append(
            OCRPage(
                page=page_no,
                text="",
                spans=[],
                width=int(item.get("width") or 0),
                height=int(item.get("height") or 0),
                warnings=[
                    {
                        "code": "ocr_page_timeout",
                        "severity": "warning",
                        "message": "OCR principal excedeu o timeout; página mantida em modo degradado.",
                        "engine": "tesseract",
                        "page": page_no,
                        "step": "ocr_pages",
                        "timeout_seconds": OCR_PAGE_TIMEOUT_SECONDS,
                        "cause_message": cause_message,
                    }
                ],
            )
        )

    return pages


def _ocr_pages_to_payloads(
    ocr_result: List[Any],
    page_strategy_by_page: Dict[int, Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for page in ocr_result:
        page_no = int(page.page)
        page_strategy = (page_strategy_by_page or {}).get(page_no, {})
        strategy = page_strategy.get("strategy") or "ocr_heavy"
        if strategy in {"native_text", "image_only"}:
            status = "skipped"
        else:
            status = "degraded" if getattr(page, "warnings", None) else "success"

        source = "ocr"
        if strategy == "native_text":
            source = "native_pdf"
        elif strategy == "image_only":
            source = "image_only"

        payload = {
            "page": page_no,
            "text": _safe_text(page.text),
            "source": source,
            "status": status,
            "strategy": strategy,
            "width": getattr(page, "width", None),
            "height": getattr(page, "height", None),
        }
        out.append({key: value for key, value in payload.items() if value is not None})
    return out


def _page_strategy_by_page(page_strategies: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    return {int(item["page"]): item for item in page_strategies if item.get("page")}


def _native_pages_by_page(native_pages: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    return {int(item["page"]): item for item in native_pages if item.get("page")}


def _select_pages_for_ocr(
    normalized_pages_out: List[Dict[str, Any]],
    page_strategy_by_page: Dict[int, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for item in normalized_pages_out:
        page_no = int(item.get("page") or 0)
        strategy = page_strategy_by_page.get(page_no, {}).get("strategy", "ocr_heavy")
        if strategy in {"ocr_light", "ocr_heavy"}:
            selected.append(item)
    return selected


def _build_skipped_ocr_results(
    normalized_pages_out: List[Dict[str, Any]],
    native_by_page: Dict[int, Dict[str, Any]],
    page_strategy_by_page: Dict[int, Dict[str, Any]],
) -> List[OCRPage]:
    pages: List[OCRPage] = []
    for item in normalized_pages_out:
        page_no = int(item.get("page") or 0)
        strategy = page_strategy_by_page.get(page_no, {}).get("strategy", "ocr_heavy")
        if strategy not in {"native_text", "image_only"}:
            continue
        native_text = _safe_text(native_by_page.get(page_no, {}).get("text"))
        pages.append(
            OCRPage(
                page=page_no,
                text=native_text if strategy == "native_text" else "",
                spans=[],
                width=int(item.get("width") or 0),
                height=int(item.get("height") or 0),
            )
        )
    return pages


def _ocr_pages_to_layout_spans(ocr_result: List[Any]) -> List[Dict[str, Any]]:
    spans_out: List[Dict[str, Any]] = []

    for page in ocr_result:
        page_no = int(page.page)
        spans = getattr(page, "spans", []) or []

        for sp in spans:
            bbox = getattr(sp, "bbox", None)
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue

            text = _safe_text(getattr(sp, "text", None))
            if not text:
                continue

            spans_out.append(
                {
                    "page": page_no,
                    "text": text,
                    "bbox": [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])],
                }
            )

    return spans_out


def _merge_native_and_ocr_pages(
    native_pages: List[Dict[str, Any]],
    ocr_pages_payload: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    native_by_page = {int(p["page"]): p for p in native_pages}
    ocr_by_page = {int(p["page"]): p for p in ocr_pages_payload}

    merged: List[Dict[str, Any]] = []
    all_pages = sorted(set(native_by_page.keys()) | set(ocr_by_page.keys()))

    for page_no in all_pages:
        native_page = native_by_page.get(page_no)
        ocr_page = ocr_by_page.get(page_no)

        native_text = _safe_text(native_page.get("text") if native_page else "")
        ocr_text = _safe_text(ocr_page.get("text") if ocr_page else "")

        native_score = _page_quality_score(native_text)
        ocr_score = _page_quality_score(ocr_text)

        if native_score >= 2.5 and len(native_text) >= max(20, int(len(ocr_text) * 0.6)):
            merged.append(
                {
                    "page": page_no,
                    "text": native_text,
                    "source": "native_pdf",
                }
            )
        elif ocr_score > 0:
            merged.append(
                {
                    "page": page_no,
                    "text": ocr_text,
                    "source": "ocr",
                }
            )
        else:
            ocr_source = ocr_page.get("source") if ocr_page else None
            merged.append(
                {
                    "page": page_no,
                    "text": native_text or ocr_text,
                    "source": "native_pdf" if native_text else ocr_source or "ocr",
                }
            )

    return merged


def _page_doc_type(page_text: str) -> str:
    subtype = classify_page_subtype(page_text or "")
    value = subtype.get("value") or "unknown"

    if value == "unknown":
        return "DOCUMENTO"

    return str(value).upper()


def _build_subdocuments(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not pages:
        return []

    subdocs: List[Dict[str, Any]] = []
    current: Dict[str, Any] | None = None

    for page in sorted(pages, key=lambda x: int(x["page"])):
        page_no = int(page["page"])
        page_text = _safe_text(page.get("text"))
        doc_type = _page_doc_type(page_text)

        if current is None:
            current = {
                "subdoc_id": f"subdoc_{len(subdocs) + 1:03d}",
                "doc_type": doc_type,
                "pages": [page_no],
                "page_map": [{"page": page_no, "text": page_text}],
            }
            continue

        if doc_type != current["doc_type"] and doc_type != "DOCUMENTO":
            current["text"] = "\n\n".join(item["text"] for item in current["page_map"]).strip()
            subdocs.append(current)

            current = {
                "subdoc_id": f"subdoc_{len(subdocs) + 1:03d}",
                "doc_type": doc_type,
                "pages": [page_no],
                "page_map": [{"page": page_no, "text": page_text}],
            }
        else:
            current["pages"].append(page_no)
            current["page_map"].append({"page": page_no, "text": page_text})

    if current is not None:
        current["text"] = "\n\n".join(item["text"] for item in current["page_map"]).strip()
        subdocs.append(current)

    return subdocs


def _set_text_literal(dm: DocumentMemory, text: str, metodo: str, confianca: float) -> DocumentMemory:
    if dm.layer2 is None:
        return dm

    dm.layer2.texto_ocr_literal = ProvenancedString(
        valor=text,
        fonte=FONTE,
        metodo=metodo,
        estado="confirmado",
        confianca=confianca,
    )
    return dm


def decompose_pdf_into_subdocuments(dm: DocumentMemory) -> DocumentMemory:
    if dm.layer1 is None or not dm.layer1.artefatos:
        return dm

    artefato = dm.layer1.artefatos[0]
    path = Path(artefato.uri)

    if not path.exists() or path.suffix.lower() != ".pdf":
        return dm

    native_pages = _extract_native_pdf_pages(path)
    strategy = _decide_extraction_strategy(native_pages)
    page_strategies = classify_pdf_page_strategies(native_pages)
    page_strategy_by_page = _page_strategy_by_page(page_strategies)
    native_by_page = _native_pages_by_page(native_pages)

    dm = _make_signal(dm, "extraction_strategy_v1", {"strategy": strategy})
    dm = _make_signal(dm, "page_strategy_v1", {"version": 1, "pages": page_strategies})

    if strategy == "native":
        subdocs = _build_subdocuments(native_pages)
        dm = _make_signal(dm, "subdocuments_v1", subdocs)

        if dm.layer2 and dm.layer2.texto_ocr_literal is None:
            dm = _set_text_literal(
                dm,
                text=_reconstruct_full_text(native_pages),
                metodo="native_pdf_text",
                confianca=0.95,
            )

        return dm

    normalization_started = perf_counter()
    normalized_pages = normalize_pdf_pages(str(path), lang="por+eng")
    normalization_duration = elapsed_ms(normalization_started)
    normalized_pages_out = _normalize_page_images_to_dicts(normalized_pages)
    _append_normalization_events(
        dm,
        normalized_pages_out,
        duration_ms=normalization_duration,
    )
    dm = _make_signal(dm, "normalized_pages_v1", normalized_pages_out)
    ocr_warnings = _collect_page_warnings(normalized_pages_out)
    if ocr_warnings:
        dm = _make_signal(dm, "ocr_warnings_v1", ocr_warnings)

    ocr_candidates = _select_pages_for_ocr(normalized_pages_out, page_strategy_by_page)
    ocr_started = perf_counter()
    try:
        ocr_result = ocr_pages(ocr_candidates)
    except RuntimeError as exc:
        if not _is_ocr_timeout_exception(exc):
            raise
        ocr_result = _build_degraded_ocr_result(ocr_candidates, exc)
    ocr_duration = elapsed_ms(ocr_started)
    ocr_result.extend(_build_skipped_ocr_results(normalized_pages_out, native_by_page, page_strategy_by_page))
    ocr_result = sorted(ocr_result, key=lambda page: int(page.page))
    _append_ocr_events(
        dm,
        ocr_result,
        page_strategy_by_page,
        duration_ms=ocr_duration,
    )

    ocr_warnings.extend(_collect_ocr_warnings(ocr_result))
    if ocr_warnings:
        dm = _make_signal(dm, "ocr_warnings_v1", ocr_warnings)

    ocr_pages_payload = _ocr_pages_to_payloads(ocr_result, page_strategy_by_page)
    layout_spans = _ocr_pages_to_layout_spans(ocr_result)

    dm = _make_signal(dm, "ocr_pages_v1", ocr_pages_payload)
    dm = _make_signal(dm, "layout_spans_v1", layout_spans)

    if strategy == "hybrid":
        final_pages = _merge_native_and_ocr_pages(native_pages, ocr_pages_payload)
        metodo = "hybrid_native_plus_ocr"
        confianca = 0.93
    else:
        final_pages = ocr_pages_payload
        metodo = "normalized_pdf_pages_plus_tesseract_per_page_with_spans"
        confianca = 0.92 if layout_spans else 0.90

    subdocs = _build_subdocuments(final_pages)
    dm = _make_signal(dm, "subdocuments_v1", subdocs)

    if dm.layer2 and dm.layer2.texto_ocr_literal is None:
        dm = _set_text_literal(
            dm,
            text=_reconstruct_full_text(final_pages),
            metodo=metodo,
            confianca=confianca,
        )

    return dm
