from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from pypdf import PdfReader


@dataclass
class PreflightSignals:
    media_type: str
    page_count: int
    has_native_text: bool
    native_rotation: int
    is_pdf: bool
    original_filename: Optional[str]


def _get_primary_artifact_path(dm) -> Optional[Path]:
    layer1 = getattr(dm, "layer1", None)
    artefatos = getattr(layer1, "artefatos", None) or []
    if not artefatos:
        return None
    uri = getattr(artefatos[0], "uri", None)
    if not uri:
        return None
    return Path(uri)


def _read_pdf_preflight(path: Path) -> tuple[int, bool, int]:
    page_count = 1
    has_native_text = False
    native_rotation = 0

    try:
        reader = PdfReader(str(path))
        page_count = len(reader.pages)
        if page_count > 0:
            first_page = reader.pages[0]
            try:
                native_rotation = int(first_page.get("/Rotate", 0) or 0)
            except Exception:
                native_rotation = 0

            try:
                extracted = first_page.extract_text() or ""
                has_native_text = len(extracted.strip()) >= 50
            except Exception:
                has_native_text = False
    except Exception:
        pass

    return page_count, has_native_text, native_rotation


def collect_preflight_signals(dm) -> PreflightSignals:
    media_type = getattr(getattr(dm, "layer1", None), "midia", None)
    media_type_value = getattr(media_type, "value", media_type) or "desconhecido"
    artifact_path = _get_primary_artifact_path(dm)

    page_count = 1
    has_native_text = False
    native_rotation = 0
    is_pdf = False

    if artifact_path and artifact_path.suffix.lower() == ".pdf":
        is_pdf = True
        page_count, has_native_text, native_rotation = _read_pdf_preflight(artifact_path)

    return PreflightSignals(
        media_type=media_type_value,
        page_count=page_count,
        has_native_text=has_native_text,
        native_rotation=native_rotation,
        is_pdf=is_pdf,
        original_filename=(getattr(getattr(dm, "layer0", None), "original_filename", None)),
    )


def preflight_to_dict(signals: PreflightSignals) -> dict:
    return asdict(signals)
