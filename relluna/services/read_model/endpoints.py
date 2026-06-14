from typing import Optional, List

from fastapi import APIRouter, Query, HTTPException
from pydantic import ValidationError

from .store import ReadModelStore
from .causal_timeline_model import build_causal_timeline_from_dm, CausalTimeline
from relluna.services.read_model.text_search import search_read_models_text
from relluna.services.read_model import store as read_model_store
from relluna.infra import mongo_store
from relluna.core.document_memory import DocumentMemory

# Prefixo separado para não conflitar com /documents da API principal
router = APIRouter(prefix="/read-model", tags=["read-model"])


@router.get("/documents")
async def list_documents(
    q: Optional[str] = Query(None, description="Busca por texto (OCR, narrativa, etc.)"),
    patient: Optional[str] = Query(None, description="Filtro por paciente"),
    provider: Optional[str] = Query(None, description="Filtro por prestador"),
    cid: Optional[str] = Query(None, description="Filtro por CID"),
    date: Optional[str] = Query(None, description="Data canônica exata em ISO"),
    doc_type: Optional[str] = Query(None, description="Tipo documental canônico"),
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
        patient=patient,
        provider=provider,
        cid=cid,
        date=date,
        doc_type=doc_type,
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
    patient: Optional[str] = Query(None, description="Filtro por paciente"),
    provider: Optional[str] = Query(None, description="Filtro por prestador"),
    cid: Optional[str] = Query(None, description="Filtro por CID"),
    date: Optional[str] = Query(None, description="Data canônica exata em ISO"),
    doc_type: Optional[str] = Query(None, description="Tipo documental canônico"),
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
        patient=patient,
        provider=provider,
        cid=cid,
        date=date,
        doc_type=doc_type,
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


@router.get("/documents/{document_id}/causal_timeline", response_model=CausalTimeline)
async def get_causal_timeline(document_id: str) -> CausalTimeline:
    """
    Retrieve causal timeline graph for a document.

    Returns events (Layer3) and causal links (Layer2.causal_link_v1) for visualization.
    Each link includes visual metadata (color, thickness) for frontend rendering.

    Args:
        document_id: Document ID to fetch timeline for

    Returns:
        CausalTimeline with eventos and grafo (causal links)

    Raises:
        HTTPException 404: Document not found
        HTTPException 422: Document lacks Layer2 or Layer3 evidence
    """
    try:
        dm_dict = await mongo_store.get(document_id)
        if not dm_dict:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

        dm = DocumentMemory.model_validate(dm_dict)
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document format: {str(e)[:100]}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load document: {str(e)[:100]}",
        )

    timeline = build_causal_timeline_from_dm(document_id, dm)
    if not timeline:
        raise HTTPException(
            status_code=422,
            detail="Document lacks Layer2 (evidence signals) or Layer3 (probatory events)",
        )

    return timeline
