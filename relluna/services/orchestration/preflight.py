from dataclasses import dataclass
from typing import Optional
from pypdf import PdfReader


@dataclass
class PreflightSignals:
    media_type: str
    page_count: int
    has_native_text: bool
    orientation_score: Optional[float]
    rotation: Optional[int]


def collect_preflight_signals(dm) -> PreflightSignals:
    artefato = dm.layer1.artefatos[0]
    path = artefato.uri

    page_count = 1
    has_text = False
    rotation = 0

    if path.lower().endswith(".pdf"):
        try:
            reader = PdfReader(path)
            page_count = len(reader.pages)

            first_page = reader.pages[0]
            text = first_page.extract_text() or ""
            has_text = len(text.strip()) > 50

            rotation = first_page.get("/Rotate", 0)

        except Exception:
            pass

    return PreflightSignals(
        media_type=dm.layer1.midia.value,
        page_count=page_count,
        has_native_text=has_text,
        orientation_score=None,  # adicionamos depois
        rotation=rotation,
    )