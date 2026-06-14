"""
Tests for evidence tracing and citation functionality in Kausal engine.

Validates that causal links include proper rastreabilidade (citations)
pointing to the original events in documents.
"""

from __future__ import annotations

from datetime import datetime, UTC

import pytest

from relluna.core.document_memory import (
    ArtefatoBruto,
    DocumentMemory,
    EvidenceRef,
    Layer0Custodia,
    Layer1Artefatos,
    Layer2Evidence,
    Layer3Evidence,
    MediaType,
    OriginType,
    ProbatoryEvent,
)
from relluna.services.causal.engine import (
    infer_causal_links,
    enrich_events_with_citations,
    persist_causal_links_to_layer2,
)


@pytest.fixture
def dm_basic() -> DocumentMemory:
    """Create basic DocumentMemory for evidence tracing tests."""
    return DocumentMemory(
        layer0=Layer0Custodia(
            documentid="evidence_test_001",
            contentfingerprint="f" * 64,
            ingestiontimestamp=datetime.now(UTC),
            ingestionagent="test_evidence",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[ArtefatoBruto(id="art_1", tipo="original", uri="test.pdf")],
        ),
    )


def test_enrich_events_without_citations(dm_basic):
    """Validate that events without citations get enriched with placeholders."""
    dm_basic.layer2 = Layer2Evidence()
    dm_basic.layer3 = Layer3Evidence(
        eventos_probatorios=[
            ProbatoryEvent(
                event_id="evt_1",
                event_type="acidente",
                title="Acidente",
                date_iso="2024-01-01T00:00:00Z",
                entities={"cid": "T20.0"},
                confidence=1.0,
                citations=[],  # Empty citations
            )
        ]
    )

    # Enrich
    dm_enriched = enrich_events_with_citations(dm_basic)

    # Check that event now has citations
    assert len(dm_enriched.layer3.eventos_probatorios) == 1
    event = dm_enriched.layer3.eventos_probatorios[0]
    assert len(event.citations) > 0
    assert event.citations[0].kind == "probatory_event"
    assert event.citations[0].uri == "document://evidence_test_001"


def test_enrich_events_preserve_existing_citations(dm_basic):
    """Validate that existing citations are not overwritten."""
    dm_basic.layer2 = Layer2Evidence()
    original_ref = EvidenceRef(
        kind="original",
        uri="document://original.pdf",
        page=5,
        snippet="Original snippet",
    )
    dm_basic.layer3 = Layer3Evidence(
        eventos_probatorios=[
            ProbatoryEvent(
                event_id="evt_1",
                event_type="acidente",
                title="Acidente",
                date_iso="2024-01-01T00:00:00Z",
                entities={"cid": "T20.0"},
                confidence=1.0,
                citations=[original_ref],
            )
        ]
    )

    # Enrich
    dm_enriched = enrich_events_with_citations(dm_basic)

    # Check that original citation is preserved
    event = dm_enriched.layer3.eventos_probatorios[0]
    assert len(event.citations) == 1
    assert event.citations[0].uri == "document://original.pdf"


def test_causal_links_include_citations():
    """Validate that CausalLinks inherit citations from source events."""
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="citation_test",
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

    # Create events with citations
    ref_evt1 = EvidenceRef(
        kind="probatory",
        uri="document://test.pdf",
        page=1,
        snippet="Acidente no trabalho",
        source_path="page:1/doc:CAT",
    )
    ref_evt2 = EvidenceRef(
        kind="probatory",
        uri="document://test.pdf",
        page=2,
        snippet="Diagnóstico confirmado",
        source_path="page:2/doc:Atestado",
    )

    dm.layer3 = Layer3Evidence(
        eventos_probatorios=[
            ProbatoryEvent(
                event_id="evt_001",
                event_type="acidente",
                title="Acidente Elétrico",
                date_iso="2024-01-15T10:30:00Z",
                entities={"cid": "T20.0", "provider_activity": "eletricista"},
                confidence=1.0,
                citations=[ref_evt1],
            ),
            ProbatoryEvent(
                event_id="evt_002",
                event_type="diagnostico",
                title="Lesão",
                date_iso="2024-01-20T14:00:00Z",
                entities={"cid": "T21.0"},
                confidence=0.95,
                citations=[ref_evt2],
            ),
        ]
    )

    # Infer links (which should include citations)
    links = infer_causal_links(dm)

    # Check that at least one link exists
    assert len(links) > 0

    # Check that link has citations
    evt_001_to_002_links = [
        lnk for lnk in links if lnk.event_a_id == "evt_001" and lnk.event_b_id == "evt_002"
    ]
    assert len(evt_001_to_002_links) > 0

    link = evt_001_to_002_links[0]
    assert link.citations is not None
    assert len(link.citations) > 0

    # Validate citation references both events
    citation_refs = [c.kind for c in link.citations]
    assert "source_event" in citation_refs or "target_event" in citation_refs


def test_citations_persisted_to_layer2():
    """Validate that citations are included in Layer2 persistence."""
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="persist_citation_test",
            contentfingerprint="b" * 64,
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

    dm.layer3 = Layer3Evidence(
        eventos_probatorios=[
            ProbatoryEvent(
                event_id="evt_001",
                event_type="acidente",
                title="Acidente",
                date_iso="2024-01-15T10:30:00Z",
                entities={"cid": "T20.0", "provider_activity": "eletricista"},
                confidence=1.0,
            ),
            ProbatoryEvent(
                event_id="evt_002",
                event_type="diagnostico",
                title="Lesão",
                date_iso="2024-01-20T14:00:00Z",
                entities={"cid": "T21.0"},
                confidence=0.95,
            ),
        ]
    )

    # Infer and persist
    links = infer_causal_links(dm)
    dm = persist_causal_links_to_layer2(dm, links)

    # Check that causal_link_v1 exists and includes citations
    assert "causal_link_v1" in dm.layer2.sinais_documentais
    sinal = dm.layer2.sinais_documentais["causal_link_v1"]

    import json

    links_json = json.loads(sinal.valor)
    assert len(links_json) > 0

    # Check first link has citations field
    first_link = links_json[0]
    assert "citations" in first_link


def test_citation_completeness():
    """Validate that each citation includes required fields."""
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="citation_completeness",
            contentfingerprint="c" * 64,
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

    dm.layer3 = Layer3Evidence(
        eventos_probatorios=[
            ProbatoryEvent(
                event_id="evt_001",
                event_type="acidente",
                title="Acidente",
                date_iso="2024-01-15T10:30:00Z",
                entities={"cid": "T20.0", "provider_activity": "eletricista"},
                confidence=1.0,
            ),
            ProbatoryEvent(
                event_id="evt_002",
                event_type="diagnostico",
                title="Lesão",
                date_iso="2024-01-20T14:00:00Z",
                entities={"cid": "T21.0"},
                confidence=0.95,
            ),
        ]
    )

    links = infer_causal_links(dm)
    assert len(links) > 0

    for link in links:
        for citation in (link.citations or []):
            # Each citation should have minimal required fields
            assert citation.kind is not None
            assert citation.uri is not None
            assert citation.provenance_status is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
