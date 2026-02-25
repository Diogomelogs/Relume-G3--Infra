from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from relluna.core.document_memory import DocumentMemory, Layer0Custodia, Layer1Artefatos, MediaType, OriginType, ArtefatoBruto
from relluna.infra.mongo.document_store import MongoDocumentStore


# --- Fake pymongo collection/db -------------------------------------------------

class FakeCollection:
    def __init__(self):
        self._data: dict[str, dict[str, Any]] = {}

    def replace_one(self, query: dict, doc: dict, upsert: bool = False):
        _id = query["_id"]
        self._data[_id] = doc

    def find_one(self, query: dict, projection: Optional[dict] = None):
        _id = query["_id"]
        doc = self._data.get(_id)
        if not doc:
            return None
        if projection == {"_id": 1}:
            return {"_id": doc["_id"]}
        return dict(doc)  # copy


class FakeDB:
    def __init__(self):
        self._cols: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str):
        if name not in self._cols:
            self._cols[name] = FakeCollection()
        return self._cols[name]


# --- Helpers --------------------------------------------------------------------

def _dm_min(docid: str) -> DocumentMemory:
    layer0 = Layer0Custodia(
        documentid=docid,
        contentfingerprint="abc",
        ingestiontimestamp=__import__("datetime").datetime.utcnow(),
        ingestionagent="test",
        authenticitystate=None,
        custodychain=[],
        versiongraph=[],
        integrityproofs=[],
    )
    layer1 = Layer1Artefatos(
        midia=MediaType.documento,
        origem=OriginType.digital_nativo,
        artefatos=[
            ArtefatoBruto(
                id="x",
                tipo="original",
                uri="file:///tmp/x",
            )
        ],
    )
    return DocumentMemory(version="v0.1.0", layer0=layer0.model_dump(mode="python"), layer1=layer1.model_dump(mode="python"))


# --- Tests ----------------------------------------------------------------------

def test_store_save_and_get_roundtrip():
    db = FakeDB()
    store = MongoDocumentStore(db)  # type: ignore[arg-type]

    dm = _dm_min("doc-1")
    store.save(dm)

    out = store.get("doc-1")
    assert out is not None
    assert (out.layer0["documentid"] if isinstance(out.layer0, dict) else out.layer0.documentid) == "doc-1"


def test_store_exists():
    db = FakeDB()
    store = MongoDocumentStore(db)  # type: ignore[arg-type]

    assert store.exists("doc-2") is False
    store.save(_dm_min("doc-2"))
    assert store.exists("doc-2") is True
