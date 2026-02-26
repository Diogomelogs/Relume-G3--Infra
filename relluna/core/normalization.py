from __future__ import annotations

from datetime import datetime
from typing import Optional

from relluna.core.document_memory import (
    DocumentMemory,
    Layer4SemanticNormalization,
)


def _extract_temporal_str(dm: DocumentMemory) -> Optional[str]:
    """
    Retorna string temporal priorizando layer3.estimativa_temporal.valor.

    - Se layer3 for dict: usa ["estimativa_temporal"]["valor"]
    - Se layer3 for modelo: usa .estimativa_temporal.valor
    - Fallback: layer2.data_exif.valor (ou string direta)

    Sempre devolve string ISO ('YYYY-MM-DD...' ou None).
    """
    # 1) Prioriza Layer3
    if dm.layer3 is not None:
        if isinstance(dm.layer3, dict):
            est = dm.layer3.get("estimativa_temporal")
        else:
            est = getattr(dm.layer3, "estimativa_temporal", None)

        if est is not None:
            # string direta
            if isinstance(est, str):
                return est

            # dict com "valor"
            if isinstance(est, dict):
                v = est.get("valor")
                if isinstance(v, str):
                    return v
                if isinstance(v, datetime):
                    return v.isoformat()
                return None

            # ProvenancedString ou similar
            v = getattr(est, "valor", None)
            if isinstance(v, str):
                return v
            if isinstance(v, datetime):
                return v.isoformat()

    # 2) Fallback: Layer2.data_exif
    if dm.layer2 is not None:
        exif = getattr(dm.layer2, "data_exif", None)
        if exif is not None:
            if isinstance(exif, str):
                return exif

            if isinstance(exif, dict):
                v = exif.get("valor")
                if isinstance(v, str):
                    return v
                if isinstance(v, datetime):
                    return v.isoformat()
                return None

            v = getattr(exif, "valor", None)
            if isinstance(v, str):
                return v
            if isinstance(v, datetime):
                return v.isoformat()

    return None


def _to_datetime(value: str) -> Optional[datetime]:
    """
    Converte string ISO para datetime, ou None se não der.
    """
    if not isinstance(value, str):
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.fromisoformat(value[:10])
        except ValueError:
            return None


def _ensure_layer3_est_str(dm: DocumentMemory) -> None:
    """
    Garante que dm.layer3.estimativa_temporal.valor seja string (ISO),
    como exigem os testes de promotion.
    """
    if dm.layer3 is None:
        return

    # Caso dict
    if isinstance(dm.layer3, dict):
        est = dm.layer3.get("estimativa_temporal")
        if isinstance(est, dict):
            v = est.get("valor")
            if isinstance(v, datetime):
                est["valor"] = v.isoformat()
        return

    # Caso modelo
    est = getattr(dm.layer3, "estimativa_temporal", None)
    if est is None:
        return

    v = getattr(est, "valor", None)
    if isinstance(v, datetime):
        est.valor = v.isoformat()


def normalize_to_layer4(dm: DocumentMemory) -> DocumentMemory:
    """
    Normalização para Layer4 (MVP).

    - sempre cria layer4
    - nunca inventa data se não existe (data_canonica permanece None)
    - prefere layer3.estimativa_temporal sobre layer2.data_exif
    - gera `periodo` a partir de data_canonica quando disponível

    Aqui, data_canonica vira *datetime* (para os testes de contrato).
    """
    l4 = Layer4SemanticNormalization()

    valor_str = _extract_temporal_str(dm)
    if isinstance(valor_str, str):
        dt = _to_datetime(valor_str)
        if dt is not None:
            # Para os testes de contrato: datetime
            l4.data_canonica = dt
            l4.periodo = f"{dt.year:04d}-{dt.month:02d}"

    dm.layer4 = l4
    return dm


def promote_temporal_to_layer4(dm: DocumentMemory) -> DocumentMemory:
    """
    Canonicalização temporal robusta (v0.2.0):
    prioridade:
      1) layer3.estimativa_temporal.valor (se existir) -> YYYY-MM-DD
      2) layer2.data_exif.valor (imagem) -> parse EXIF -> YYYY-MM-DD
      3) layer2.texto_ocr_literal.valor (PDF/documento) -> heurística de datas -> YYYY-MM-DD
      4) senão: data_canonica = None

    Observação: NÃO muta Layer3. Apenas promove para Layer4.
    """
    from datetime import datetime
    import re

    # Garantir Layer4 sempre existe
    if getattr(dm, "layer4", None) is None:
        dm.layer4 = Layer4()  # type: ignore[name-defined]

    def _iso_from_any_date_str(s: str) -> str | None:
        s = (s or "").strip()
        if not s:
            return None

        # Já em ISO?
        m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", s)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

        # dd/mm/yyyy
        m = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", s)
        if m:
            dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
            return f"{yyyy}-{mm}-{dd}"

        # dd mon yyyy (PT-BR) ex: 20 MAI 2025
        months = {
            "JAN": "01", "FEV": "02", "MAR": "03", "ABR": "04", "MAI": "05", "JUN": "06",
            "JUL": "07", "AGO": "08", "SET": "09", "OUT": "10", "NOV": "11", "DEZ": "12",
        }
        m = re.search(r"\b(\d{1,2})\s+([A-ZÇ]{3})\s+(\d{4})\b", s.upper())
        if m and m.group(2) in months:
            dd = f"{int(m.group(1)):02d}"
            mm = months[m.group(2)]
            yyyy = m.group(3)
            return f"{yyyy}-{mm}-{dd}"

        # EXIF comum: 2015:12:26 16:13:12  ou  2011.01.03 18:21:14
        m = re.search(r"\b(\d{4})[:.](\d{2})[:.](\d{2})\b", s)
        if m:
            yyyy, mm, dd = m.group(1), m.group(2), m.group(3)
            return f"{yyyy}-{mm}-{dd}"

        return None

    # 1) Layer3 estimativa_temporal
    est = None
    try:
        est = getattr(getattr(dm, "layer3", None), "estimativa_temporal", None)
        est = getattr(est, "valor", None)
    except Exception:
        est = None

    iso = _iso_from_any_date_str(str(est)) if est else None

    # 2) EXIF
    if not iso:
        exif = None
        try:
            exif = getattr(getattr(dm, "layer2", None), "data_exif", None)
            exif = getattr(exif, "valor", None)
        except Exception:
            exif = None
        iso = _iso_from_any_date_str(str(exif)) if exif else None

    # 3) OCR (PDF)
    if not iso:
        ocr = None
        try:
            ocr_obj = getattr(getattr(dm, "layer2", None), "texto_ocr_literal", None)
            if isinstance(ocr_obj, dict):
                ocr = ocr_obj.get("valor")
            else:
                ocr = getattr(ocr_obj, "valor", None) if ocr_obj is not None else None
        except Exception:
            ocr = None

        # Heurística: tenta capturar a primeira data “forte” no texto
        if ocr:
            iso = _iso_from_any_date_str(ocr)

    # Promove para Layer4
    dm.layer4.data_canonica = iso  # type: ignore[attr-defined]

    # Mantém compat com testes/contrato: sempre preencher rótulos mínimos
    if getattr(dm.layer4, "periodo", None) is None:
        dm.layer4.periodo = "desconhecido" if iso is None else iso  # type: ignore[attr-defined]
    if getattr(dm.layer4, "rotulo_temporal", None) is None:
        dm.layer4.rotulo_temporal = "sem_data" if iso is None else iso  # type: ignore[attr-defined]

    return dm

