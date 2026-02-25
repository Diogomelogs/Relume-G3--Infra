from __future__ import annotations

from datetime import datetime, UTC
from typing import List, Optional

from relluna.core.document_memory import (
    DocumentMemory,
    Layer4SemanticNormalization,
)
from relluna.services.read_model.models import DocumentReadModel


def _layer4_date_str(l4: Layer4SemanticNormalization) -> Optional[str]:
    dc = l4.data_canonica
    if isinstance(dc, datetime):
        return dc.strftime("%Y-%m-%d")
    if isinstance(dc, str):
        return dc[:10]
    return None


def _safe_text(valor) -> Optional[str]:
    if valor and isinstance(valor, str):
        return valor.strip()
    return None


def project_dm_to_read_model(dm: DocumentMemory) -> DocumentReadModel:
    document_id = dm.layer0.documentid
    media_type = dm.layer1.midia.value if dm.layer1 else None

    title = (
        f"{dm.layer1.midia.value} {document_id[:8]}"
        if dm.layer1
        else document_id
    )

    summary = "Documento processado"

    # ---------------------------
    # Layer4 (canônico)
    # ---------------------------
    date_canonical: Optional[str] = None
    period_label: Optional[str] = None
    tags: List[str] = []
    entities: List[dict] = []

    if isinstance(dm.layer4, Layer4SemanticNormalization):
        date_canonical = _layer4_date_str(dm.layer4)
        period_label = dm.layer4.periodo
        tags = list(dm.layer4.tags or [])

        for ent in dm.layer4.entidades or []:
            entities.append(
                {
                    "kind": ent.kind,
                    "label": ent.label,
                }
            )

    # ---------------------------
    # TEXTO BASE (Layer2)
    # ---------------------------
    ocr_text = None
    transcription_text = None

    if dm.layer2:
        if getattr(dm.layer2, "texto_ocr_literal", None):
            ocr_text = _safe_text(dm.layer2.texto_ocr_literal.valor)

        if getattr(dm.layer2, "transcricao_literal", None):
            transcription_text = _safe_text(dm.layer2.transcricao_literal.valor)

    # ---------------------------
    # search_text (nunca vazio)
    # ---------------------------
    parts = [document_id, title, summary]

    if date_canonical:
        parts.append(date_canonical)

    if tags:
        parts.extend(tags)

    if entities:
        parts.extend(e["label"] for e in entities)

    if ocr_text:
        parts.append(ocr_text)

    if transcription_text:
        parts.append(transcription_text)

    search_text = " ".join(str(p) for p in parts if p) or document_id

    now = datetime.now(UTC)

    return DocumentReadModel(
        document_id=document_id,
        media_type=media_type,
        title=title,
        summary=summary,
        date_canonical=date_canonical,
        period_label=period_label,
        tags=tags,
        entities=entities,
        search_text=search_text,
        created_at=now,
        updated_at=now,
    )