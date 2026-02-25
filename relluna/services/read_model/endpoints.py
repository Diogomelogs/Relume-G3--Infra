from typing import Optional, List

from fastapi import APIRouter, Query

from .store import ReadModelStore
from relluna.services.read_model.text_search import search_read_models_text
from relluna.services.read_model import store as read_model_store

# Prefixo separado para não conflitar com /documents da API principal
router = APIRouter(prefix="/read-model", tags=["read-model"])


@router.get("/documents")
async def list_documents(
    q: Optional[str] = Query(None, description="Busca por texto (OCR, narrativa, etc.)"),
    start_date: Optional[str] = Query(None, description="Data inicial ISO ex: 1958-01-01"),
    end_date: Optional[str] = Query(None, description="Data final ISO ex: 1958-12-31"),
    tipo_evento: Optional[str] = Query(None, description="Tipo de evento/categoria da Layer3"),
    tags: Optional[List[str]] = Query(None, description="Lista de tags da Layer4"),
    limit: int = Query(20, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    store = ReadModelStore()

    return await store.search(
        q=q,
        start_date=start_date,
        end_date=end_date,
        tipo_evento=tipo_evento,
        tags=tags,
        limit=limit,
        skip=skip,
    )


@router.get("/search")
async def search_documents(
    q: Optional[str] = Query(None, description="Texto livre"),
    start_date: Optional[str] = Query(None, description="Data inicial ISO"),
    end_date: Optional[str] = Query(None, description="Data final ISO"),
    tipo_evento: Optional[str] = Query(None, description="Tipo de evento da Layer3"),
    tags: Optional[List[str]] = Query(None, description="Tags da Layer4"),
    limit: int = Query(20, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    store = ReadModelStore()

    return await store.search(
        q=q,
        start_date=start_date,
        end_date=end_date,
        tipo_evento=tipo_evento,
        tags=tags,
        limit=limit,
        skip=skip,
    )
@router.get("/search_text")
def search_text(
    q: str = Query(..., min_length=1, description="Consulta textual"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Busca textual simples sobre o READ MODEL.
    """

    # Descobre método de listagem disponível
    if hasattr(read_model_store, "list_all"):
        read_models = read_model_store.list_all()
    elif hasattr(read_model_store, "all"):
        read_models = read_model_store.all()
    elif hasattr(read_model_store, "iter_all"):
        read_models = list(read_model_store.iter_all())
    else:
        read_models = []

    hits = search_read_models_text(read_models, query=q, limit=limit)

    return {
        "query": q,
        "count": len(hits),
        "hits": [
            {
                "documentid": h.documentid,
                "score": h.score,
                "snippet": h.snippet,
            }
            for h in hits
        ],
    }