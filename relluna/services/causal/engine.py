"""
Motor de Kausal: infere hipóteses de nexo causal entre eventos probatórios.

Este módulo aplica regras jurídicas sobre o fluxo do pipeline para identificar
relações causais entre eventos, sempre com base legal explícita.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from relluna.core.document_memory import DocumentMemory, EvidenceRef
from relluna.services.causal.rules_previdenciario import KAUSAL_RULES
from relluna.services.causal.types import CausalLink
from relluna.services.evidence.signals import load_critical_signal_json


def infer_causal_links(dm: DocumentMemory) -> List[CausalLink]:
    """
    Aplica regras KAUSAL aos eventos de Layer3 para gerar hipóteses de nexo causal.

    Fluxo:
    1. Carrega eventos probatórios de Layer3
    2. Para cada par (evento_a, evento_b) em cronologia:
       - Aplica 6 regras determinísticas
       - Se confiança > 0.5 → cria CausalLink com lastro
    3. Retorna lista de CausalLinks com review_state="auto"

    Args:
        dm: DocumentMemory com Layer3 já preenchida

    Returns:
        Lista de CausalLink, ordenada por data do evento_a
    """
    if not dm.layer3 or not dm.layer3.eventos_probatorios:
        return []

    events = dm.layer3.eventos_probatorios
    canonical = _load_entities_canonical(dm)
    links: List[CausalLink] = []

    # Itera pares de eventos (i < j mantém cronologia)
    for i, event_a in enumerate(events):
        for j, event_b in enumerate(events):
            if i >= j:
                continue

            # Aplica cada regra
            for rule in KAUSAL_RULES:
                try:
                    if rule.condition(event_a, event_b, canonical):
                        # Construir explicação concreta
                        explanation = _render_explanation(
                            rule.explanation_template,
                            event_a,
                            event_b,
                            canonical,
                        )

                        # Criar aresta
                        link = CausalLink(
                            event_a_id=event_a.event_id or f"evt_{i}",
                            event_b_id=event_b.event_id or f"evt_{j}",
                            event_a_date=_parse_date(event_a.date_iso),
                            event_b_date=_parse_date(event_b.date_iso),
                            link_type=rule.name.lower().replace(" ", "_"),
                            confidence=rule.confidence_base,
                            rule_id=rule.rule_id,
                            rule_explanation=explanation,
                            citations=_build_citations(event_a, event_b, dm),
                            review_state="auto",
                        )

                        # Não duplicar regras (uma aresta por par por regra)
                        if not _link_exists(links, link):
                            links.append(link)
                except Exception as e:
                    # Log de erro sem bloquear
                    dm.layer0.add_processing_event(
                        status="warning",
                        code="causal_rule_error",
                        message=f"Erro ao aplicar {rule.rule_id}: {str(e)}",
                    )

    # Ordenar por data do evento A
    links.sort(key=lambda x: x.event_a_date)
    return links


def persist_causal_links_to_layer2(dm: DocumentMemory, links: List[CausalLink]) -> DocumentMemory:
    """
    Persiste CausalLinks no sinal versionado Layer2.sinais_documentais["causal_link_v1"].

    Args:
        dm: DocumentMemory
        links: Lista de CausalLink gerada

    Returns:
        dm com Layer2 atualizado
    """
    if not dm.layer2:
        return dm

    # Serializar CausalLinks para JSON
    links_json = json.dumps(
        [
            {
                "event_a_id": link.event_a_id,
                "event_b_id": link.event_b_id,
                "event_a_date": link.event_a_date.isoformat(),
                "event_b_date": link.event_b_date.isoformat(),
                "link_type": link.link_type,
                "confidence": link.confidence,
                "rule_id": link.rule_id,
                "rule_explanation": link.rule_explanation,
                "review_state": link.review_state,
                "visual_color": link.visual_color,
                "visual_thickness": link.visual_thickness,
            }
            for link in links
        ],
        ensure_ascii=False,
        indent=2,
    )

    # Salvar como sinal determinístico
    from relluna.core.document_memory import ProvenancedString

    dm.layer2.sinais_documentais["causal_link_v1"] = ProvenancedString(
        valor=links_json,
        fonte="relluna.services.causal.engine",
        confianca=0.95,
    )

    return dm


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _load_entities_canonical(dm: DocumentMemory) -> Dict[str, Any]:
    """Carrega entidades canônicas de Layer2.sinais_documentais."""
    data = load_critical_signal_json(dm, "entities_canonical_v1")
    if isinstance(data, dict):
        return data
    return {}


def _parse_date(date_iso: Optional[str]) -> datetime:
    """Parse ISO date string ou retorna agora."""
    if not date_iso:
        return datetime.now()
    try:
        return datetime.fromisoformat(date_iso)
    except ValueError:
        return datetime.now()


def _render_explanation(
    template: str,
    event_a: Any,
    event_b: Any,
    canonical: Dict[str, Any],
) -> str:
    """Renderiza template de explicação com valores concretos."""
    try:
        cid_a = event_a.entities.get("cid", "") if event_a.entities else ""
        cid_b = event_b.entities.get("cid", "") if event_b.entities else ""
        date_a = _parse_date(event_a.date_iso)
        date_b = _parse_date(event_b.date_iso)
        dias = (date_b - date_a).days

        return template.format(
            cid=cid_b or "N/A",
            cid_a=cid_a or "N/A",
            cid_b=cid_b or "N/A",
            atividade=canonical.get("provider_activity", "N/A"),
            dias=dias,
            data_a=date_a.strftime("%d/%m/%Y"),
            data_b=date_b.strftime("%d/%m/%Y"),
            data_pericia=date_b.strftime("%d/%m/%Y"),
            doc_a=event_a.event_type or "Evento A",
            doc_b=event_b.event_type or "Evento B",
        )
    except Exception:
        # Fallback se template falhar
        return "Nexo identificado por análise causal determinística"


def _build_citations(event_a: Any, event_b: Any, dm: DocumentMemory) -> List[EvidenceRef]:
    """Cria EvidenceRef apontando para os dois eventos nos documentos."""
    refs = []

    # Referência ao evento A
    if event_a.citations:
        refs.extend(event_a.citations[:1])  # Primeira citação de A

    # Referência ao evento B
    if event_b.citations:
        refs.extend(event_b.citations[:1])  # Primeira citação de B

    return refs


def _link_exists(links: List[CausalLink], new_link: CausalLink) -> bool:
    """Verifica se CausalLink já existe (evita duplicatas)."""
    for link in links:
        if (
            link.event_a_id == new_link.event_a_id
            and link.event_b_id == new_link.event_b_id
            and link.rule_id == new_link.rule_id
        ):
            return True
    return False


__all__ = [
    "infer_causal_links",
    "persist_causal_links_to_layer2",
]
