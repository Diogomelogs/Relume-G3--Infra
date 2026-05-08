# arquivo: relluna/infra/mongo_store.py

from typing import Optional, List

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from relluna.infra.secrets import get_secret

from relluna.core.document_memory import DocumentMemory

_client: Optional[AsyncIOMotorClient] = None
_collection: Optional[AsyncIOMotorCollection] = None


async def init(
    uri: Optional[str] = None,
    db_name: str = "relluna",
    collection_name: str = "documentos_memoria",
) -> None:
    """
    Inicializa o cliente Mongo e a collection padrão.

    Deve ser chamado no startup do FastAPI (ver api.py).
    """
    global _client, _collection

    if uri is None:
        uri = get_secret("MONGODB_URI", default="mongodb://localhost:27017")

    _client = AsyncIOMotorClient(uri)
    db = _client[db_name]
    _collection = db[collection_name]


async def close() -> None:
    """
    Fecha o cliente Mongo. Deve ser chamado no shutdown da app.
    """
    global _client, _collection

    if _client is not None:
        _client.close()
    _client = None
    _collection = None


def _get_collection() -> AsyncIOMotorCollection:
    if _collection is None:
        raise RuntimeError("mongo_store não inicializado. Chame init() no startup da app.")
    return _collection


async def save(dm: DocumentMemory) -> None:
    """
    Salva (upsert) um Documento-Memória inteiro.

    Chave de upsert: layer0.documentid (UUID do DM).
    """
    coll = _get_collection()
    doc = dm.model_dump()  # se quiser usar aliases, ajuste aqui

    await coll.replace_one(
        {"layer0.documentid": dm.layer0.documentid},
        doc,
        upsert=True,
    )


async def get(documentid: str) -> Optional[DocumentMemory]:
    coll = _get_collection()
    raw = await coll.find_one({"layer0.documentid": documentid})
    if not raw:
        return None
    return DocumentMemory.model_validate(raw)


async def list_all(limit: int = 50, skip: int = 0) -> List[DocumentMemory]:
    coll = _get_collection()
    cursor = coll.find().skip(skip).limit(limit)
    docs: List[DocumentMemory] = []
    async for raw in cursor:
        docs.append(DocumentMemory.model_validate(raw))
    return docs
