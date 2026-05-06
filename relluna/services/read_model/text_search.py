from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, List, Tuple


_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _norm(s: str) -> str:
    """
    Normalização simples e determinística:
    - lowercase
    - remove acentos
    - mantém apenas [a-z0-9] para tokenização
    """
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s


def _tokens(s: str) -> List[str]:
    s = _norm(s)
    return _WORD_RE.findall(s)


def _safe_get(obj: Any, path: str, default: Any = None) -> Any:
    """
    path tipo: "a.b.c"
    Funciona com dicts e objetos (pydantic models também).
    """
    cur = obj
    for key in path.split("."):
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(key, None)
        else:
            cur = getattr(cur, key, None)
    return cur if cur is not None else default


@dataclass(frozen=True)
class TextSearchHit:
    documentid: str
    score: float
    snippet: str


def build_search_corpus(read_model: Any) -> Tuple[str, str]:
    """
    Retorna (full_text, preferred_snippet_source).
    Adapte por convenção, sem depender de um schema rígido.
    """
    # Campos comuns no read-model (tente vários nomes sem quebrar)
    title = _safe_get(read_model, "titulo", "") or _safe_get(read_model, "title", "")
    text = _safe_get(read_model, "texto", "") or _safe_get(read_model, "text", "")
    summary = _safe_get(read_model, "resumo", "") or _safe_get(read_model, "summary", "")
    tags = _safe_get(read_model, "tags", []) or _safe_get(read_model, "layer4.tags", [])
    entities = _safe_get(read_model, "entidades", []) or _safe_get(read_model, "entities", [])
    patient = _safe_get(read_model, "patient", "")
    provider = _safe_get(read_model, "provider", "")
    cids = _safe_get(read_model, "cids", []) or []
    event_types = _safe_get(read_model, "event_types", []) or []
    doc_type = _safe_get(read_model, "doc_type", "")
    search_text = _safe_get(read_model, "search_text", "")

    # Normaliza coleções
    if isinstance(tags, (list, tuple)):
        tags_text = " ".join(str(x) for x in tags if x is not None)
    else:
        tags_text = str(tags)

    if isinstance(entities, (list, tuple)):
        ent_text = " ".join(str(x) for x in entities if x is not None)
    else:
        ent_text = str(entities)

    # Corpus: título+tags+entities recebem peso “natural” porque tokens repetem
    corpus = " ".join(
        part
        for part in [
            str(title),
            str(doc_type),
            str(patient),
            str(provider),
            " ".join(str(x) for x in cids if x is not None),
            " ".join(str(x) for x in event_types if x is not None),
            str(tags_text),
            str(ent_text),
            str(summary),
            str(text),
            str(search_text),
        ]
        if part
    ).strip()

    # Fonte de snippet: prefira o texto longo, senão resumo/título
    snippet_src = str(text or summary or title or corpus)
    return corpus, snippet_src


def _score_match(corpus: str, query: str) -> float:
    """
    Score determinístico:
    - conta quantos tokens da query aparecem no corpus
    - + bônus se query inteira aparece como substring normalizada
    """
    q_toks = _tokens(query)
    if not q_toks:
        return 0.0

    c_toks = set(_tokens(corpus))
    if not c_toks:
        return 0.0

    hits = sum(1 for t in q_toks if t in c_toks)
    base = hits / max(1, len(q_toks))

    # bônus: substring (frase) presente
    qn = _norm(query)
    cn = _norm(corpus)
    bonus = 0.25 if qn and qn in cn else 0.0

    return float(min(1.0, base + bonus))


def _make_snippet(snippet_source: str, query: str, max_len: int = 240) -> str:
    s = (snippet_source or "").strip()
    if not s:
        return ""

    qn = _norm(query)
    sn = _norm(s)

    if qn and qn in sn:
        # tenta recortar em torno do match (aproximação por índice em string normalizada)
        idx = sn.find(qn)
        # como normalização pode alterar tamanho, fazemos um fallback simples por proporção
        start = max(0, idx - 60)
        end = min(len(s), start + max_len)
        out = s[start:end].strip()
        if start > 0:
            out = "…" + out
        if end < len(s):
            out = out + "…"
        return out

    # fallback: começo do texto
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def search_read_models_text(
    read_models: Iterable[Any],
    query: str,
    limit: int = 20,
    min_score: float = 0.15,
) -> List[TextSearchHit]:
    """
    Busca textual simples (baseline), para agora.
    Depois evolui para BM25/FTS/Postgres/Mongo text index sem quebrar contrato.
    """
    hits: List[TextSearchHit] = []
    q = (query or "").strip()
    if not q:
        return hits

    for rm in read_models:
        docid = (
            _safe_get(rm, "documentid", "")
            or _safe_get(rm, "document_id", "")
            or _safe_get(rm, "layer0.documentid", "")
        )
        if not docid:
            continue

        corpus, snippet_src = build_search_corpus(rm)
        score = _score_match(corpus, q)
        if score < min_score:
            continue

        hits.append(
            TextSearchHit(
                documentid=str(docid),
                score=score,
                snippet=_make_snippet(snippet_src, q),
            )
        )

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[: max(1, int(limit))]
