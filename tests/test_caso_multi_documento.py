"""
Tests for Caso multi-documento: aggregating multiple DocumentMemory into one case.
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
from relluna.services.causal.caso import Caso, merge_timelines, infer_cross_document_links


def _make_dm(doc_id: str, events: list[ProbatoryEvent]) -> DocumentMemory:
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid=doc_id,
            contentfingerprint="a" * 64,
            ingestiontimestamp=datetime.now(UTC),
            ingestionagent="test",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[ArtefatoBruto(id="art_1", tipo="original", uri=f"{doc_id}.pdf")],
        ),
        layer2=Layer2Evidence(),
    )
    dm.layer3 = Layer3Evidence(eventos_probatorios=events)
    return dm


@pytest.fixture
def dm_cat():
    """Documento 1: CAT (Comunicação de Acidente de Trabalho)."""
    return _make_dm("doc_cat_001", [
        ProbatoryEvent(
            event_id="cat_evt_001",
            event_type="acidente",
            title="Acidente Elétrico",
            date_iso="2024-06-15T10:00:00Z",
            entities={"cid": "T20.0", "provider_activity": "eletricista"},
            confidence=1.0,
        ),
    ])


@pytest.fixture
def dm_atestado():
    """Documento 2: Atestado médico com diagnóstico."""
    return _make_dm("doc_atestado_001", [
        ProbatoryEvent(
            event_id="atestado_evt_001",
            event_type="diagnostico",
            title="Lesão Muscular",
            date_iso="2024-06-20T14:00:00Z",
            entities={"cid": "T21.0"},
            confidence=0.95,
        ),
    ])


@pytest.fixture
def dm_pericia():
    """Documento 3: Perícia INSS."""
    return _make_dm("doc_pericia_001", [
        ProbatoryEvent(
            event_id="pericia_evt_001",
            event_type="perícia",
            title="Perícia INSS",
            date_iso="2024-07-25T11:00:00Z",
            entities={"cid": "T20.0"},
            confidence=0.99,
        ),
    ])


def test_merge_timelines_dedup(dm_cat, dm_atestado):
    """Timeline merge deduplica por event_id."""
    merged = merge_timelines([dm_cat, dm_atestado])
    assert len(merged) == 2
    ids = [e.event_id for e in merged]
    assert "cat_evt_001" in ids
    assert "atestado_evt_001" in ids


def test_merge_timelines_ordering(dm_cat, dm_atestado, dm_pericia):
    """Timeline merge ordena por data."""
    merged = merge_timelines([dm_pericia, dm_cat, dm_atestado])
    assert len(merged) == 3
    assert merged[0].event_id == "cat_evt_001"
    assert merged[1].event_id == "atestado_evt_001"
    assert merged[2].event_id == "pericia_evt_001"


def test_cross_document_causal_links(dm_cat, dm_atestado):
    """Nexo causal inter-documento: acidente (doc1) → diagnóstico (doc2)."""
    links = infer_cross_document_links([dm_cat, dm_atestado])
    assert len(links) > 0

    cross_link = next(
        (lnk for lnk in links
         if lnk.event_a_id == "cat_evt_001" and lnk.event_b_id == "atestado_evt_001"),
        None,
    )
    assert cross_link is not None, "Deve haver nexo entre acidente (doc1) e diagnóstico (doc2)"


def test_caso_build(dm_cat, dm_atestado, dm_pericia):
    """Caso.build() consolida timeline e grafo causal."""
    caso = Caso(case_id="caso_001", title="Caso Eletricista")
    caso.add_document(dm_cat)
    caso.add_document(dm_atestado)
    caso.add_document(dm_pericia)
    caso.build()

    assert len(caso.merged_events) == 3
    assert len(caso.causal_links) >= 1
    assert caso.metadata["total_documents"] == 3
    assert caso.metadata["total_events"] == 3
    assert "doc_cat_001" in caso.metadata["document_ids"]


def test_caso_empty():
    """Caso sem documentos retorna vazio."""
    caso = Caso(case_id="empty").build()
    assert len(caso.merged_events) == 0
    assert len(caso.causal_links) == 0


def test_pericia_confirms_cross_document(dm_cat, dm_pericia):
    """Perícia (doc2) confirma acidente (doc1) — mesmo CID inter-doc."""
    links = infer_cross_document_links([dm_cat, dm_pericia])

    pericia_link = next(
        (lnk for lnk in links
         if lnk.event_a_id == "cat_evt_001"
         and lnk.event_b_id == "pericia_evt_001"
         and "pericia" in lnk.rule_id.lower()),
        None,
    )
    assert pericia_link is not None, "Perícia deve confirmar acidente inter-documento"
    assert pericia_link.confidence >= 0.80


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
