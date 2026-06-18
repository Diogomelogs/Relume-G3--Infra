"""
Regras anti-nexo: heurísticas que enfraquecem a tese causal.

O sistema deve ser honesto sobre limitações. Anti-nexo não nega o nexo,
mas sinaliza fatores que exigem revisão humana.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List

from relluna.services.causal.types import CausalLink


def apply_anti_nexo(links: List[CausalLink], events: List[Any]) -> List[CausalLink]:
    """
    Aplica heurísticas anti-nexo a cada CausalLink existente.

    Adiciona weakening_factors e marca review_state="needs_review" quando apropriado.
    """
    events_by_id = {e.event_id: e for e in events}

    for link in links:
        evt_a = events_by_id.get(link.event_a_id)
        evt_b = events_by_id.get(link.event_b_id)
        if not evt_a or not evt_b:
            continue

        factors: List[str] = []

        if _diagnostico_tardio(evt_a, evt_b):
            factors.append("diagnóstico_tardio: CID aparece >5 anos após exposição")

        if _ocupacoes_conflitantes(evt_a, evt_b, events):
            factors.append("ocupações_conflitantes: mesmo CID em atividades diferentes")

        if _intervalo_sem_tratamento(evt_a, evt_b, events):
            factors.append("intervalo_sem_tratamento: >2 anos sem eventos médicos intermediários")

        if factors:
            link.weakening_factors = factors
            link.review_state = "needs_review"

    return links


def _diagnostico_tardio(evt_a: Any, evt_b: Any) -> bool:
    """CID aparece >5 anos após exposição → enfraquece nexo."""
    if not evt_a.date_iso or not evt_b.date_iso:
        return False
    try:
        date_a = datetime.fromisoformat(evt_a.date_iso)
        date_b = datetime.fromisoformat(evt_b.date_iso)
        return (date_b - date_a).days > 5 * 365
    except ValueError:
        return False


def _ocupacoes_conflitantes(evt_a: Any, evt_b: Any, events: List[Any]) -> bool:
    """Mesmo CID em 2 atividades diferentes → ambiguidade sobre causa."""
    cid_b = (evt_b.entities or {}).get("cid", "")
    if not cid_b:
        return False

    cid_prefix = cid_b[:3]
    activities = set()

    for evt in events:
        evt_cid = (evt.entities or {}).get("cid", "")
        if evt_cid and evt_cid[:3] == cid_prefix:
            activity = (evt.entities or {}).get("provider_activity", "")
            if activity:
                activities.add(activity.lower().strip())

    return len(activities) >= 2


def _intervalo_sem_tratamento(evt_a: Any, evt_b: Any, events: List[Any]) -> bool:
    """
    >2 anos entre eventos médicos consecutivos com mesmo CID → presunção enfraquecida.
    """
    cid_a = (evt_a.entities or {}).get("cid", "")
    if not cid_a:
        return False

    cid_prefix = cid_a[:3]

    related_dates = []
    for evt in events:
        evt_cid = (evt.entities or {}).get("cid", "")
        if evt_cid and evt_cid[:3] == cid_prefix and evt.date_iso:
            try:
                related_dates.append(datetime.fromisoformat(evt.date_iso))
            except ValueError:
                continue

    if len(related_dates) < 2:
        return False

    related_dates.sort()
    for i in range(len(related_dates) - 1):
        gap = (related_dates[i + 1] - related_dates[i]).days
        if gap > 2 * 365:
            return True

    return False


__all__ = ["apply_anti_nexo"]
