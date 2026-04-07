import json

from .date_extractor import extract_dates
from .date_anchor import anchor_dates_to_layout
from .event_builder import build_events


def build_timeline(layer2, layer3):

    text = layer2["texto_ocr_literal"]["valor"]

    layout_spans = json.loads(
        layer2["sinais_documentais"]["layout_spans_v1"]["valor"]
    )

    doc_type = layer3["tipo_documento"]["valor"]

    dates = extract_dates(text)

    anchored = anchor_dates_to_layout(dates, layout_spans)

    events = build_events(anchored, doc_type)

    return events