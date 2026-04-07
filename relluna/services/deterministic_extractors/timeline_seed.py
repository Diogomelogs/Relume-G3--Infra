from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Any, Dict, List, Optional

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.types_basic import ProvenancedString


_RE_DATE_DMY = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def _prov_json(payload: Any, fonte: str, metodo: str) -> ProvenancedString:
    return ProvenancedString(
        valor=json.dumps(payload, ensure_ascii=False),
        fonte=fonte,
        metodo=metodo,
        estado="confirmado",
        confianca=1.0,
        lastro=[],
    )


def _safe_load_signal_json(dm: DocumentMemory, key: str) -> Optional[Any]:
    if dm.layer2 is None:
        return None
    s = dm.layer2.sinais_documentais.get(key)
    if not s or not getattr(s, "valor", None):
        return None
    try:
        return json.loads(s.valor)
    except Exception:
        return None


def seed_timeline(dm: DocumentMemory, max_events: int = 200) -> DocumentMemory:
    """
    Cria eventos mínimos determinísticos:
    - date_iso
    - snippet
    - (opcional) page/bbox aproximado se layout_spans_v1 existir
    Persiste em layer2.sinais_documentais["timeline_seed_v1"] como JSON string.
    """
    if dm.layer2 is None or dm.layer2.texto_ocr_literal is None:
        return dm

    text = (dm.layer2.texto_ocr_literal.valor or "")
    if not text.strip():
        return dm

    layout_spans = _safe_load_signal_json(dm, "layout_spans_v1")
    # index simples para procurar bbox
    spans: List[Dict[str, Any]] = layout_spans if isinstance(layout_spans, list) else []

    events: List[Dict[str, Any]] = []
    seen = set()

    for m in _RE_DATE_DMY.finditer(text):
        d, mo, y = m.group(1), m.group(2), m.group(3)
        date_iso = f"{y}-{int(mo):02d}-{int(d):02d}"
        key = (date_iso, m.start())
        if key in seen:
            continue
        seen.add(key)

        # snippet: 160 chars ao redor
        a = max(0, m.start() - 80)
        b = min(len(text), m.end() + 80)
        snippet = text[a:b].strip().replace("\n", " ")

        # tentativa de bbox: procurar span que contenha a data literal
        bbox = None
        page = None
        literal = m.group(0)
        for sp in spans:
            if literal in (sp.get("text") or ""):
                bbox = sp.get("bbox")
                page = sp.get("page")
                break

        seed_id = sha256(f"{date_iso}|{snippet}".encode("utf-8")).hexdigest()[:16]

        events.append(
            {
                "seed_id": seed_id,
                "date_iso": date_iso,
                "page": page,
                "bbox": bbox,
                "snippet": snippet,
                "date_literal": literal,
            }
        )

        if len(events) >= max_events:
            break

    if not events:
        return dm

    dm.layer2.sinais_documentais["timeline_seed_v1"] = _prov_json(
        events,
        fonte="deterministic_extractors.timeline_seed",
        metodo="regex_dates_v1+layout_match_optional",
    )
    return dm