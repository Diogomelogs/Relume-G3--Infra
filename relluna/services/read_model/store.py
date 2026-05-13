from typing import Any, Dict, List, Optional

from relluna.infra.mongo import get_db
from .schema import ReadModelDocument

_MEMORY_READ_MODEL_STORE: Dict[str, dict] = {}


def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _contains_value(value: Any, expected: str) -> bool:
    if value is None:
        return False
    expected_norm = str(expected).strip().lower()
    if isinstance(value, (list, tuple, set)):
        return any(_contains_value(item, expected_norm) for item in value)
    return expected_norm in str(value).strip().lower()


def _matches_filters(
    doc: Dict[str, Any],
    *,
    q: Optional[str] = None,
    periodo: Optional[str] = None,
    tipo_evento: Optional[str] = None,
    tags: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    patient: Optional[str] = None,
    provider: Optional[str] = None,
    cid: Optional[str] = None,
    date: Optional[str] = None,
    doc_type: Optional[str] = None,
) -> bool:
    if q and not _contains_value(_safe_get(doc, "search_text"), q):
        return False
    if periodo and _safe_get(doc, "period_label") != periodo:
        return False
    if tipo_evento and not _contains_value(_safe_get(doc, "event_types"), tipo_evento):
        return False
    if tags:
        doc_tags = _safe_get(doc, "tags", []) or []
        if not all(tag in doc_tags for tag in tags):
            return False
    date_canonical = _safe_get(doc, "date_canonical")
    if date and date_canonical != date:
        return False
    if start_date and (not date_canonical or date_canonical < start_date):
        return False
    if end_date and (not date_canonical or date_canonical > end_date):
        return False
    if patient and not _contains_value(_safe_get(doc, "patient"), patient):
        return False
    if provider and not _contains_value(_safe_get(doc, "provider"), provider):
        return False
    if cid and not _contains_value(_safe_get(doc, "cids"), cid):
        return False
    if doc_type and _safe_get(doc, "doc_type") != doc_type:
        return False
    return True


class ReadModelStore:
    def __init__(self) -> None:
        self.col = None
        try:
            db = get_db()
            self.col = db["read_model_documents"]
        except Exception:
            self.col = None

    async def upsert(self, doc: ReadModelDocument) -> None:
        payload = doc.model_dump(mode="python")
        if self.col is None:
            _MEMORY_READ_MODEL_STORE[doc.document_id] = payload
            return

        result = self.col.update_one(
            {"document_id": doc.document_id},
            {"$set": payload},
            upsert=True,
        )
        if hasattr(result, "__await__"):
            await result

    async def search(
        self,
        q: Optional[str] = None,
        periodo: Optional[str] = None,
        tipo_evento: Optional[str] = None,
        tags: Optional[List[str]] = None,
        patient: Optional[str] = None,
        provider: Optional[str] = None,
        cid: Optional[str] = None,
        date: Optional[str] = None,
        doc_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
        skip: int = 0,
    ) -> List[dict]:
        query: dict = {}
        if self.col is None:
            docs = list(_MEMORY_READ_MODEL_STORE.values())
            filtered = [
                doc for doc in docs
                if _matches_filters(
                    doc,
                    q=q,
                    periodo=periodo,
                    tipo_evento=tipo_evento,
                    tags=tags,
                    patient=patient,
                    provider=provider,
                    cid=cid,
                    date=date,
                    doc_type=doc_type,
                    start_date=start_date,
                    end_date=end_date,
                )
            ]
            filtered.sort(key=lambda doc: _safe_get(doc, "date_canonical") or "", reverse=True)
            if skip:
                filtered = filtered[skip:]
            return filtered[:limit]

        if q:
            query["search_text"] = {"$regex": q, "$options": "i"}

        if periodo:
            query["period_label"] = periodo

        if tipo_evento:
            query["event_types"] = tipo_evento

        if tags:
            query["tags"] = {"$all": tags}

        if patient:
            query["patient"] = {"$regex": patient, "$options": "i"}

        if provider:
            query["provider"] = {"$regex": provider, "$options": "i"}

        if cid:
            query["cids"] = cid

        if doc_type:
            query["doc_type"] = doc_type

        if date:
            query["date_canonical"] = date

        if start_date or end_date:
            range_filter: dict = {}
            if start_date:
                range_filter["$gte"] = start_date
            if end_date:
                range_filter["$lte"] = end_date
            query["date_canonical"] = range_filter

        cursor = (
            self.col.find(query)
            .sort("date_canonical", -1)
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

        results = [
            doc for doc in results
            if _matches_filters(
                doc,
                q=q,
                periodo=periodo,
                tipo_evento=tipo_evento,
                tags=tags,
                patient=patient,
                provider=provider,
                cid=cid,
                date=date,
                doc_type=doc_type,
                start_date=start_date,
                end_date=end_date,
            )
        ]

        if skip:
            results = results[skip:]

        return results[:limit]


def list_all() -> List[dict]:
    return list(_MEMORY_READ_MODEL_STORE.values())


def all() -> List[dict]:
    return list_all()


def iter_all():
    return iter(list_all())
