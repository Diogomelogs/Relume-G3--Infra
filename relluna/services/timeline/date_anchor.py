"""
STATUS: legado

Este módulo pertence ao caminho paralelo `relluna/services/timeline/*`.
Não é a fonte oficial atual da timeline de produto.

Fonte oficial atual:
- `Layer3.eventos_probatorios`
- `relluna/services/read_model/timeline_builder.py`

Mantido apenas para referência e compatibilidade pontual enquanto a limpeza de
legados não termina.
"""

def anchor_dates_to_layout(dates, layout_spans):

    anchored = []

    for d in dates:

        for span in layout_spans:

            if d["raw"] in span["text"]:

                anchored.append({
                    "date_iso": d["iso"],
                    "page": span["page"],
                    "bbox": span["bbox"],
                    "text": span["text"]
                })

    return anchored
