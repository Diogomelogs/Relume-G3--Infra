from __future__ import annotations

import json
from typing import Any, Dict, List

from relluna.core.document_memory import DocumentMemory


def _load_json_signal(dm: DocumentMemory, key: str):
    if dm.layer2 is None:
        return None
    sig = dm.layer2.sinais_documentais.get(key)
    if not sig or not getattr(sig, "valor", None):
        return None
    try:
        return json.loads(sig.valor)
    except Exception:
        return None


def _group_spans_by_page(dm: DocumentMemory) -> Dict[int, List[Dict[str, Any]]]:
    spans = _load_json_signal(dm, "layout_spans_v1")
    grouped: Dict[int, List[Dict[str, Any]]] = {}

    if not isinstance(spans, list):
        return grouped

    for sp in spans:
        page = sp.get("page")
        if page is None:
            continue
        grouped.setdefault(int(page), []).append(sp)

    for page_no, page_spans in grouped.items():
        grouped[page_no] = sorted(
            page_spans,
            key=lambda s: (
                float((s.get("bbox") or [0, 0, 0, 0])[1]),
                float((s.get("bbox") or [0, 0, 0, 0])[0]),
            ),
        )

    return grouped


def split_document_by_page(dm: DocumentMemory) -> List[Dict[str, Any]]:
    spans_by_page = _group_spans_by_page(dm)

    subdocs = _load_json_signal(dm, "subdocuments_v1")
    if isinstance(subdocs, list) and subdocs:
        pages: List[Dict[str, Any]] = []
        for sub in subdocs:
            for item in sub.get("page_map", []):
                page_no = item.get("page")
                if page_no is None:
                    continue

                pages.append(
                    {
                        "page": int(page_no),
                        "text": item.get("text", ""),
                        "spans": spans_by_page.get(int(page_no), []),
                        "subdoc_id": sub.get("subdoc_id"),
                        "subdoc_type": sub.get("doc_type"),
                    }
                )
        if pages:
            return sorted(pages, key=lambda x: x["page"])

    if spans_by_page:
        pages = []
        for page_no, spans in spans_by_page.items():
            text = " ".join((s.get("text") or "").strip() for s in spans)
            pages.append({"page": page_no, "text": text, "spans": spans})
        return sorted(pages, key=lambda x: x["page"])

    return []