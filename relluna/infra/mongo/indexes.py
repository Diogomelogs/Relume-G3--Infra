from __future__ import annotations

from pymongo.database import Database


# Índices principais da coleção de DocumentMemory

async def ensure_indexes(db):
    col = db["document_memories"]

    await col.create_index(
        "layer0.documentid",
        unique=True,
        name="uniq_documentid",
    )

    await col.create_index(
        "layer0.ingestiontimestamp",
        name="idx_ingestion_ts",
    )


# Índices do Read Model

async def ensure_read_model_indexes(db):
    col = db["read_model_documents"]

    await col.create_index(
        [("search_text", "text")],
        name="idx_search_text",
    )

    await col.create_index(
        [("data_canonica", -1)],
        name="idx_data_canonica",
    )

    await col.create_index(
        [("periodo", 1)],
        name="idx_periodo",
    )

    await col.create_index(
        [("tipo_evento", 1)],
        name="idx_tipo_evento",
    )
