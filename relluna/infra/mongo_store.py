import os
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient
from relluna.core.document_memory import DocumentMemory
from relluna.infra.secrets import get_secret

# -----------------------------
# In-memory fallback
# -----------------------------

_MEMORY_STORE = {}

_client = None
_db = None


def _mongo_enabled() -> bool:
    return bool(os.getenv("MONGO_URI") or os.getenv("MONGODB_URI"))


def get_mongo_client():
    global _client
    if not _mongo_enabled():
        return None

    if _client is None:
        uri = (
            get_secret("MONGO_URI", default="")
            or get_secret("MONGODB_URI", default="")
        )
        _client = AsyncIOMotorClient(uri)
    return _client


def get_database():
    global _db
    if not _mongo_enabled():
        return None

    if _db is None:
        client = get_mongo_client()
        db_name = (
            get_secret("MONGO_DB", default="")
            or get_secret("MONGO_DB_NAME", default="")
            or get_secret("MONGODB_DB", default="")
            or "relluna"
        )
        _db = client[db_name]
    return _db


def get_collection():
    db = get_database()
    if db is None:
        return None
    return db["document_memory"]


# -----------------------------
# Interface pública
# -----------------------------

async def save(dm: DocumentMemory):
    if not _mongo_enabled():
        _MEMORY_STORE[dm.layer0.documentid] = dm
        return

    coll = get_collection()
    data = dm.model_dump(mode="json")
    await coll.replace_one(
        {"layer0.documentid": dm.layer0.documentid},
        data,
        upsert=True,
    )


async def get(documentid: str) -> Optional[DocumentMemory]:
    if not _mongo_enabled():
        return _MEMORY_STORE.get(documentid)

    coll = get_collection()
    data = await coll.find_one({"layer0.documentid": documentid})
    if not data:
        return None
    data.pop("_id", None)
    return DocumentMemory.model_validate(data)


async def exists(documentid: str) -> bool:
    if not _mongo_enabled():
        return documentid in _MEMORY_STORE

    coll = get_collection()
    count = await coll.count_documents(
        {"layer0.documentid": documentid},
        limit=1,
    )
    return count > 0
