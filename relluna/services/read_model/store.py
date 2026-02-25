from datetime import datetime, timezone
from typing import List, Optional

from relluna.infra.mongo import get_db
from .schema import ReadModelDocument


class ReadModelStore:
    def __init__(self) -> None:
        db = get_db()
        self.col = db["read_model_documents"]

    async def upsert(self, doc: ReadModelDocument) -> None:
        await self.col.update_one(
            {"document_id": doc.document_id},
            {"$set": doc.model_dump()},
            upsert=True,
        )

    async def search(
        self,
        q: Optional[str] = None,
        periodo: Optional[str] = None,
        tipo_evento: Optional[str] = None,
        tags: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
        skip: int = 0,
    ) -> List[dict]:
        query: dict = {}

        if q:
            query["$text"] = {"$search": q}

        if periodo:
            query["periodo"] = periodo

        if tipo_evento:
            query["tipo_evento"] = tipo_evento

        if tags:
            query["tags"] = {"$all": tags}

        if start_date or end_date:
            range_filter: dict = {}
            if start_date:
                range_filter["$gte"] = start_date
            if end_date:
                range_filter["$lte"] = end_date
            query["data_canonica"] = range_filter

        cursor = (
            self.col.find(query)
            .sort("data_canonica", -1)
            .limit(limit + skip)
        )

        results: List[dict] = []

        # Suporta tanto cursor assíncrono (teste de contrato) quanto síncrono (Mongo real)
        if hasattr(cursor, "__aiter__"):
            async for doc in cursor:  # usado no teste unitário com mock assíncrono
                results.append(doc)
        else:
            for doc in cursor:  # usado no runtime real com pymongo Cursor
                results.append(doc)

        if skip:
            results = results[skip:]

        return results
