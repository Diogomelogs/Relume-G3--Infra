"""
STATUS: wrapper compatível legado

Pipeline paralelo anterior à consolidação da timeline oficial.
Hoje não participa do fluxo real da API e existe apenas para compatibilidade
pontual/documentação de legado.

Fonte oficial atual da timeline:
- `deterministic_extractors.timeline_seed_v2` como fallback compatível
- `Layer3.eventos_probatorios` como fonte primária
- `relluna/services/read_model/timeline_builder.py` como superfície pública
"""

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
