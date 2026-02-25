from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from pymongo.database import Database
from pymongo.collection import Collection

from relluna.core.document_memory import DocumentMemory


@dataclass(frozen=True)
class MongoDocumentStore:
    db: Database
    collection_name: str = "document_memories"

    @property
    def col(self) -> Collection:
        return self.db[self.collection_name]

    def save(self, dm: DocumentMemory) -> None:
        dm_dict = dm.model_dump(mode="python")
        docid = _extract_docid(dm_dict)
        if not docid:
            raise ValueError("DocumentMemory missing layer0.documentid")

        # _id canônico
        dm_dict["_id"] = docid

        self.col.replace_one({"_id": docid}, dm_dict, upsert=True)

    def get(self, documentid: str) -> Optional[DocumentMemory]:
        raw = self.col.find_one({"_id": documentid})
        if not raw:
            return None
        raw.pop("_id", None)
        return DocumentMemory.model_validate(raw)

    def exists(self, documentid: str) -> bool:
        return self.col.find_one({"_id": documentid}, {"_id": 1}) is not None


def _extract_docid(dm_dict: dict[str, Any]) -> str | None:
    layer0 = dm_dict.get("layer0")
    if isinstance(layer0, dict):
        return layer0.get("documentid")
    # fallback (não esperado, mas defensivo)
    try:
        return getattr(layer0, "documentid", None)
    except Exception:
        return None
