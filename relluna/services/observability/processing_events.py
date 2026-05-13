from __future__ import annotations

from time import perf_counter
from typing import Any, Dict, Optional

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.layer0 import ProcessingEvent


def elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000.0, 3)


def sanitize_processing_details(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: sanitize_processing_details(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [sanitize_processing_details(item) for item in value if item is not None]
    return value


def append_processing_event(
    dm: DocumentMemory,
    *,
    etapa: str,
    engine: str,
    status: str = "success",
    detalhes: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[float] = None,
    page_index: Optional[int] = None,
    warning_code: Optional[str] = None,
    fallback: Optional[Dict[str, Any]] = None,
    degraded_mode: Optional[str] = None,
) -> None:
    if not getattr(dm, "layer0", None):
        return

    payload = dict(detalhes or {})
    code = warning_code or payload.get("warning_code") or payload.get("code")
    page = page_index if page_index is not None else payload.get("page_index") or payload.get("page")
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    if page is not None:
        payload["page_index"] = page
    if code is not None:
        payload["warning_code"] = code
    if fallback is not None:
        payload["fallback"] = fallback
    if degraded_mode is not None:
        payload["degraded_mode"] = degraded_mode

    dm.layer0.processingevents.append(
        ProcessingEvent(
            etapa=etapa,
            engine=engine,
            status=status,
            detalhes=sanitize_processing_details(payload),
        )
    )
