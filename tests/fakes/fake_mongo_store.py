# tests/fakes/fake_mongo_store.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    # opcional: se existir no teu projeto
    from pydantic import BaseModel
except Exception:  # pragma: no cover
    BaseModel = object  # type: ignore


_STORE: Dict[str, Dict[str, Any]] = {}


def _docid_from_dm(dm: Any) -> str:
    """
    Extrai documentid de um DocumentMemory onde dm.layer0 pode ser:
    - dict (layer0["documentid"])
    - Pydantic model (layer0.documentid)
    - outro objeto com atributo documentid
    """
    layer0 = getattr(dm, "layer0", None)
    if layer0 is None:
        raise KeyError("dm.layer0 ausente")

    # dict
    if isinstance(layer0, dict):
        docid = layer0.get("documentid")
        if not docid:
            raise KeyError("dm.layer0['documentid'] ausente")
        return str(docid)

    # pydantic / objeto
    docid = getattr(layer0, "documentid", None)
    if not docid:
        raise KeyError("dm.layer0.documentid ausente")
    return str(docid)


def _to_dict(dm: Any) -> Dict[str, Any]:
    """
    Normaliza o DocumentMemory para dict para persistência estável no fake store.
    """
    # Pydantic v2
    if hasattr(dm, "model_dump") and callable(getattr(dm, "model_dump")):
        return dm.model_dump(mode="python")

    # Pydantic v1
    if hasattr(dm, "dict") and callable(getattr(dm, "dict")):
        return dm.model_dump(mode="json")


    # Já é dict
    if isinstance(dm, dict):
        return dm

    raise TypeError(f"Não sei serializar tipo: {type(dm)!r}")


# -----------------------------------------------------------------------------
# API esperada pelo tests/conftest.py (monkeypatch do mongo_store real)
# -----------------------------------------------------------------------------

async def init(*args: Any, **kwargs: Any) -> None:
    # no-op para testes
    return None


async def close(*args: Any, **kwargs: Any) -> None:
    # no-op para testes
    return None


async def save(dm: Any) -> None:
    docid = _docid_from_dm(dm)
    _STORE[docid] = _to_dict(dm)


async def get(documentid: str) -> Optional[Dict[str, Any]]:
    return _STORE.get(str(documentid))


async def delete(documentid: str) -> None:
    _STORE.pop(str(documentid), None)


async def list_all() -> List[Dict[str, Any]]:
    return list(_STORE.values())


async def count_all() -> int:
    return len(_STORE)


def clear() -> None:
    """
    Útil em fixtures. Não é obrigatório, mas ajuda.
    """
    _STORE.clear()
