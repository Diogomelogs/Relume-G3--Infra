"""
Create MongoDB indexes for the Relluna Document-Memory collection.

Usage (inside container):
    python tools/create_document_memory_indexes.py
"""

import os
import asyncio
from pprint import pprint

from motor.motor_asyncio import AsyncIOMotorClient


MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB_NAME", "relluna")
COLLECTION_NAME = os.getenv("MONGODB_COLLECTION_NAME", "document_memory")


async def create_document_memory_indexes():
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI não definida no ambiente")

    print(f"🔗 Conectando no MongoDB Atlas (db={DB_NAME}, coll={COLLECTION_NAME})...\n")
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]
    coll = db[COLLECTION_NAME]

    print("🔧 Criando índices na collection...\n")

    idx_uniq_documentid = await coll.create_index(
        "layer0.documentid",
        unique=True,
        name="uniq_documentid",
    )

    idx_ingestion_ts = await coll.create_index(
        "layer0.ingestiontimestamp",
        name="idx_ingestion_ts",
    )

    idx_midia = await coll.create_index(
        "layer1.midia",
        name="idx_midia",
    )

    print("✅ Índices criados/confirmados com sucesso:\n")
    pprint(
        {
            "uniq_documentid": idx_uniq_documentid,
            "idx_ingestion_ts": idx_ingestion_ts,
            "idx_midia": idx_midia,
        }
    )

    print("\n📚 Índices atuais na collection:\n")
    async for idx in coll.list_indexes():
        pprint(idx)

    client.close()


async def main():
    await create_document_memory_indexes()


if __name__ == "__main__":
    asyncio.run(main())
