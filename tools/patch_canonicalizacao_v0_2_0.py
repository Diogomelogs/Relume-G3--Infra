# tools/patch_canonicalizacao_v0_2_0.py
from __future__ import annotations

import re
from pathlib import Path

TARGET = Path("relluna/core/normalization.py")

NEW_FUNC = r'''
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
'''.lstrip("\n")

def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"Arquivo não encontrado: {TARGET}")

    src = TARGET.read_text(encoding="utf-8")

    # troca a função inteira por regex (mais seguro do que mexer “na mão”)
    pattern = re.compile(
        r"def\s+promote_temporal_to_layer4\s*\(.*?\):\n(?:[ \t].*\n)+",
        re.DOTALL,
    )

    m = pattern.search(src)
    if not m:
        raise SystemExit(
            "Não encontrei 'def promote_temporal_to_layer4(...)' em relluna/core/normalization.py.\n"
            "Rode: grep -RIn \"def promote_temporal_to_layer4\" relluna/core"
        )

    out = src[: m.start()] + NEW_FUNC + "\n" + src[m.end() :]

    TARGET.write_text(out, encoding="utf-8")
    print(f"[OK] Patch aplicado em: {TARGET}")

if __name__ == "__main__":
    main()