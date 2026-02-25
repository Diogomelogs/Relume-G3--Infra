from __future__ import annotations

from typing import Any, Dict, Optional

from relluna.core.document_memory import DocumentMemory


def _dump_or_value(x: Any) -> Any:
    if x is None:
        return None
    if hasattr(x, "model_dump"):
        return x.model_dump()
    return x


def to_contract(dm: DocumentMemory) -> dict:
    """
    Converte DocumentMemory (modelo interno) para dict compatível com os testes.
    Observações críticas:
      - NÃO use "if dm.layerX" (dict vazio é falsy e some do contrato).
      - Sempre inclua storage_uris dentro de layer5 quando layer5 existir (mesmo vazio).
    """
    result: Dict[str, Any] = {
        "version": dm.version,
        "layer0": {
            "documentid": dm.layer0.documentid,
            "contentfingerprint": dm.layer0.contentfingerprint,
            "ingestiontimestamp": dm.layer0.ingestiontimestamp.isoformat(),
            "ingestionagent": dm.layer0.ingestionagent,
        },
        "layer1": {
            "midia": dm.layer1.midia.value if hasattr(dm.layer1.midia, "value") else dm.layer1.midia,
            "origem": dm.layer1.origem.value if hasattr(dm.layer1.origem, "value") else dm.layer1.origem,
            "artefatos": [{"id": a.id, "tipo": a.tipo, "uri": a.uri} for a in (dm.layer1.artefatos or [])],
        },
        "layer2": None,
        "layer3": None,
        "layer4": None,
        "layer5": None,
        "layer6": None,
    }

    # ---------------- Layer 2 ----------------
    if dm.layer2 is not None:
        l2 = dm.layer2
        result["layer2"] = {
            "largura_px": _dump_or_value(getattr(l2, "largura_px", None)),
            "altura_px": _dump_or_value(getattr(l2, "altura_px", None)),
            "num_paginas": _dump_or_value(getattr(l2, "num_paginas", None)),
            "duracao_segundos": _dump_or_value(getattr(l2, "duracao_segundos", None)),
            "data_exif": _dump_or_value(getattr(l2, "data_exif", None)),
            "gps_exif": _dump_or_value(getattr(l2, "gps_exif", None)),
            "texto_ocr_literal": _dump_or_value(getattr(l2, "texto_ocr_literal", None)),
            "entidades_visuais_objetivas": [
                _dump_or_value(e) for e in (getattr(l2, "entidades_visuais_objetivas", None) or [])
            ],
        }

    # ---------------- Layer 3 ----------------
    if dm.layer3 is not None:
        result["layer3"] = _dump_or_value(dm.layer3)

    # ---------------- Layer 4 ----------------
    if dm.layer4 is not None:
        result["layer4"] = _dump_or_value(dm.layer4)

    # ---------------- Layer 5 ----------------
    if dm.layer5 is not None:
        l5 = dm.layer5

        def _list_of_derivados(name: str):
            items = getattr(l5, name, None)
            if items is None and isinstance(l5, dict):
                items = l5.get(name)
            items = items or []
            out = []
            for d in items:
                if hasattr(d, "model_dump"):
                    dd = d.model_dump()
                    out.append({"tipo": dd.get("tipo"), "uri": dd.get("uri")})
                elif isinstance(d, dict):
                    out.append({"tipo": d.get("tipo"), "uri": d.get("uri")})
                else:
                    out.append({"tipo": getattr(d, "tipo", None), "uri": getattr(d, "uri", None)})
            return out

        storage_items = getattr(l5, "storage_uris", None)
        if storage_items is None and isinstance(l5, dict):
            storage_items = l5.get("storage_uris")
        storage_items = storage_items or []

        storage_out = []
        for s in storage_items:
            if hasattr(s, "model_dump"):
                storage_out.append(s.model_dump())
            elif isinstance(s, dict):
                storage_out.append(s)
            else:
                storage_out.append({"uri": str(s)})

        persistence_state = getattr(l5, "persistence_state", None)
        if persistence_state is None and isinstance(l5, dict):
            persistence_state = l5.get("persistence_state")

        result["layer5"] = {
            "imagens_derivadas": _list_of_derivados("imagens_derivadas"),
            "audios_derivados": _list_of_derivados("audios_derivados"),
            "videos_derivados": _list_of_derivados("videos_derivados"),
            "documentos_derivados": _list_of_derivados("documentos_derivados"),
            "storage_uris": storage_out,               # SEMPRE existe se layer5 existe
            "persistence_state": persistence_state,    # pode ser None, mas a chave existe
        }

    # remove apenas chaves totalmente None (mantém dicts vazios quando existirem)
    return {k: v for k, v in result.items() if v is not None}