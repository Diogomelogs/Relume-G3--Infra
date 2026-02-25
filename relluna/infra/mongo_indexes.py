import asyncio
from relluna.infra import mongo_store

async def create_document_memory_indexes():
    coll = mongo_store.get_collection()

    await coll.create_index(
        "layer0.documentid",
        unique=True,
        name="uniq_documentid",
    )

    await coll.create_index(
        "layer0.ingestiontimestamp",
        name="idx_ingestion_ts",
    )

    await coll.create_index(
        "layer1.midia",
        name="idx_midia",
    )

def main():
    asyncio.run(create_document_memory_indexes())

if __name__ == "__main__":
    main()
