"""
Tests for anti-nexo detection: heuristics that weaken causal thesis.
"""

from __future__ import annotations

from datetime import datetime, UTC

import pytest

from relluna.core.document_memory import (
    ArtefatoBruto,
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    Layer2Evidence,
    Layer3Evidence,
    MediaType,
    OriginType,
)
from relluna.core.document_memory.layer3 import ProbatoryEvent
from relluna.services.causal.engine import infer_causal_links


def _make_dm(events: list[ProbatoryEvent]) -> DocumentMemory:
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="anti_nexo_test",
            contentfingerprint="a" * 64,
            ingestiontimestamp=datetime.now(UTC),
            ingestionagent="test",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[ArtefatoBruto(id="art_1", tipo="original", uri="test.pdf")],
        ),
        layer2=Layer2Evidence(),
    )
    dm.layer3 = Layer3Evidence(eventos_probatorios=events)
    return dm


def test_diagnostico_tardio():
    """CID aparece >5 anos após exposição → weakening_factor."""
    dm = _make_dm([
        ProbatoryEvent(
            event_id="evt_001",
            event_type="acidente",
            title="Acidente",
            date_iso="2015-01-15T10:00:00Z",
            entities={"cid": "T20.0", "provider_activity": "eletricista"},
            confidence=1.0,
        ),
        ProbatoryEvent(
            event_id="evt_002",
            event_type="diagnostico",
            title="Lesão",
            date_iso="2021-06-15T10:00:00Z",
            entities={"cid": "T21.0"},
            confidence=0.9,
        ),
    ])

    links = infer_causal_links(dm)
    assert len(links) > 0

    tardio_links = [lnk for lnk in links if lnk.weakening_factors]
    assert len(tardio_links) > 0
    assert any("diagnóstico_tardio" in f for f in tardio_links[0].weakening_factors)
    assert tardio_links[0].review_state == "needs_review"


def test_ocupacoes_conflitantes():
    """Mesmo CID em 2 atividades diferentes → weakening_factor."""
    dm = _make_dm([
        ProbatoryEvent(
            event_id="evt_001",
            event_type="acidente",
            title="Acidente Eletricista",
            date_iso="2024-01-15T10:00:00Z",
            entities={"cid": "T20.0", "provider_activity": "eletricista"},
            confidence=1.0,
        ),
        ProbatoryEvent(
            event_id="evt_002",
            event_type="diagnostico",
            title="Queimadura",
            date_iso="2024-02-15T10:00:00Z",
            entities={"cid": "T20.1", "provider_activity": "soldador"},
            confidence=0.9,
        ),
    ])

    links = infer_causal_links(dm)
    assert len(links) > 0

    conflito_links = [lnk for lnk in links if lnk.weakening_factors]
    assert len(conflito_links) > 0
    assert any("ocupações_conflitantes" in f for f in conflito_links[0].weakening_factors)


def test_intervalo_sem_tratamento():
    """>2 anos entre eventos médicos com mesmo CID → weakening_factor."""
    dm = _make_dm([
        ProbatoryEvent(
            event_id="evt_001",
            event_type="acidente",
            title="Acidente",
            date_iso="2020-01-15T10:00:00Z",
            entities={"cid": "T20.0", "provider_activity": "eletricista"},
            confidence=1.0,
        ),
        ProbatoryEvent(
            event_id="evt_002",
            event_type="diagnostico",
            title="Retorno",
            date_iso="2023-06-15T10:00:00Z",
            entities={"cid": "T20.1"},
            confidence=0.9,
        ),
    ])

    links = infer_causal_links(dm)
    assert len(links) > 0

    intervalo_links = [lnk for lnk in links if lnk.weakening_factors]
    assert len(intervalo_links) > 0
    assert any("intervalo_sem_tratamento" in f for f in intervalo_links[0].weakening_factors)


def test_no_anti_nexo_on_clean_case():
    """Caso limpo não deve ter weakening_factors."""
    dm = _make_dm([
        ProbatoryEvent(
            event_id="evt_001",
            event_type="acidente",
            title="Acidente",
            date_iso="2024-06-15T10:00:00Z",
            entities={"cid": "T20.0", "provider_activity": "eletricista"},
            confidence=1.0,
        ),
        ProbatoryEvent(
            event_id="evt_002",
            event_type="diagnostico",
            title="Lesão",
            date_iso="2024-06-20T10:00:00Z",
            entities={"cid": "T21.0"},
            confidence=0.95,
        ),
    ])

    links = infer_causal_links(dm)
    assert len(links) > 0
    for lnk in links:
        assert len(lnk.weakening_factors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
