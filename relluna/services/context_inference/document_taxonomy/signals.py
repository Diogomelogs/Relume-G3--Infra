from dataclasses import dataclass
from typing import Optional

from relluna.core.document_memory import DocumentMemory


@dataclass
class DocumentSignals:
    # Texto
    ocr_text: Optional[str] = None

    # Arquivo / mídia
    mime_type: Optional[str] = None
    file_extension: Optional[str] = None
    media_type: Optional[str] = None  # imagem, video, audio, documento

    # Evidências estruturais
    has_text: Optional[bool] = None
    has_dates: Optional[bool] = None
    has_currency: Optional[bool] = None
    has_identifiers: Optional[bool] = None

    # Evidências quantitativas
    num_pages: Optional[int] = None
    duration_seconds: Optional[float] = None
    width_px: Optional[int] = None
    height_px: Optional[int] = None


# -------------------------
# EXTRAÇÃO CANÔNICA
# -------------------------


def extract_document_signals(dm: DocumentMemory) -> DocumentSignals:
    """
    Extrai sinais observáveis de Layer1 e Layer2.

    NÃO infere.
    NÃO classifica.
    NÃO cria Layer3.
    """
    signals = DocumentSignals()

    # -------------------------
    # Layer1 — tipo de mídia / extensão
    # -------------------------
    if dm.layer1 and dm.layer1.artefatos:
        artefato = dm.layer1.artefatos[0]
        if artefato.uri:
            if "." in artefato.uri:
                signals.file_extension = artefato.uri.rsplit(".", 1)[-1].lower()

        signals.media_type = (
            dm.layer1.midia.value
            if hasattr(dm.layer1.midia, "value")
            else str(dm.layer1.midia)
        )

    # -------------------------
    # Layer2 — OCR / texto
    # -------------------------
    if dm.layer2 and dm.layer2.texto_ocr_literal:
        text = dm.layer2.texto_ocr_literal.valor
        if text:
            signals.ocr_text = text
            signals.has_text = True

            low = text.lower()
            signals.has_dates = any(k in low for k in ["data", "date", "/20", "-20"])
            signals.has_currency = any(
                k in low for k in ["r$", "$", "usd", "eur", "€"]
            )
            signals.has_identifiers = any(
                k in low for k in ["cpf", "cnpj", "rg", "id", "invoice"]
            )
        else:
            signals.has_text = False

    # -------------------------
    # Layer2 — dimensões de imagem
    # -------------------------
    if dm.layer2:
        if dm.layer2.largura_px and dm.layer2.largura_px.valor is not None:
            signals.width_px = int(dm.layer2.largura_px.valor)
        if dm.layer2.altura_px and dm.layer2.altura_px.valor is not None:
            signals.height_px = int(dm.layer2.altura_px.valor)

    # -------------------------
    # Layer2 — duração (áudio/vídeo)
    # -------------------------
    if dm.layer2 and dm.layer2.duracao_segundos:
        if dm.layer2.duracao_segundos.valor is not None:
            signals.duration_seconds = float(dm.layer2.duracao_segundos.valor)

    # -------------------------
    # Layer2 — número de páginas (PDF)
    # -------------------------
    if dm.layer2 and dm.layer2.num_paginas:
        if dm.layer2.num_paginas.valor is not None:
            signals.num_pages = int(dm.layer2.num_paginas.valor)

    return signals
