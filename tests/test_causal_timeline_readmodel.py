"""
Tests for causal timeline read model endpoint.

Validates that the read model correctly exposes causal links and events
for frontend visualization.
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
    ProbatoryEvent,
)
from relluna.services.causal.engine import infer_causal_links, persist_causal_links_to_layer2
from relluna.services.read_model.causal_timeline_model import build_causal_timeline_from_dm


@pytest.fixture
def dm_with_causal_links() -> DocumentMemory:
    """Create DocumentMemory with causal links for read model testing."""
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="readmodel_test_001",
            contentfingerprint="b" * 64,
            ingestiontimestamp=datetime.now(UTC),
            ingestionagent="test_readmodel",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="artifact_001",
                    tipo="original",
                    uri="uploads/readmodel_test_001.pdf",
                )
            ],
        ),
    )

    dm.layer2 = Layer2Evidence()
    dm.layer3 = Layer3Evidence(
        eventos_probatorios=[
            ProbatoryEvent(
                event_id="evt_001",
                event_type="acidente",
                title="Acidente no Trabalho",
                description="Queda de altura",
                date_iso="2024-01-15T10:30:00Z",
                entities={"cid": "S72.0", "provider_activity": "pedreiro"},
                confidence=1.0,
            ),
            ProbatoryEvent(
                event_id="evt_002",
                event_type="diagnostico",
                title="Fratura Confirmada",
                description="Fratura de fêmur esquerdo",
                date_iso="2024-01-20T14:00:00Z",
                entities={"cid": "S73.1"},
                confidence=0.95,
            ),
            ProbatoryEvent(
                event_id="evt_003",
                event_type="perícia",
                title="Perícia INSS",
                description="Perícia que confirma acidente laboral",
                date_iso="2024-02-15T11:00:00Z",
                entities={"cid": "S72.0"},
                confidence=0.99,
            ),
        ]
    )

    # Generate and persist causal links
    links = infer_causal_links(dm)
    dm = persist_causal_links_to_layer2(dm, links)

    return dm


def test_causal_timeline_readmodel_structure(dm_with_causal_links):
    """Validate causal timeline read model has correct structure."""
    timeline = build_causal_timeline_from_dm("readmodel_test_001", dm_with_causal_links)

    assert timeline is not None
    assert timeline.document_id == "readmodel_test_001"
    assert len(timeline.eventos) == 3
    assert len(timeline.grafo) > 0


def test_causal_timeline_eventos_mapping(dm_with_causal_links):
    """Validate that Layer3 events map correctly to timeline eventos."""
    timeline = build_causal_timeline_from_dm("readmodel_test_001", dm_with_causal_links)

    # Check event mapping
    assert timeline.eventos[0].event_id == "evt_001"
    assert timeline.eventos[0].event_type == "acidente"
    assert timeline.eventos[0].title == "Acidente no Trabalho"

    assert timeline.eventos[1].event_id == "evt_002"
    assert timeline.eventos[1].event_type == "diagnostico"

    assert timeline.eventos[2].event_id == "evt_003"
    assert timeline.eventos[2].event_type == "perícia"


def test_causal_timeline_date_formatting(dm_with_causal_links):
    """Validate that dates are formatted for display."""
    timeline = build_causal_timeline_from_dm("readmodel_test_001", dm_with_causal_links)

    # All events should have display dates
    for evento in timeline.eventos:
        assert evento.date_display is not None
        assert "/" in evento.date_display  # DD/MM/YYYY format


def test_causal_timeline_links_visual_metadata(dm_with_causal_links):
    """Validate that causal links include visual metadata."""
    timeline = build_causal_timeline_from_dm("readmodel_test_001", dm_with_causal_links)

    for link in timeline.grafo:
        assert link.seta_cor is not None
        assert link.seta_cor.startswith("#")  # Hex color
        assert len(link.seta_cor) == 7  # #RRGGBB

        assert link.seta_espessura in [1, 2, 3]
        assert link.rule_explanation is not None
        assert link.review_state in ["auto", "needs_review", "human_confirmed"]


def test_causal_timeline_metadata(dm_with_causal_links):
    """Validate that timeline metadata is computed correctly."""
    timeline = build_causal_timeline_from_dm("readmodel_test_001", dm_with_causal_links)

    assert timeline.metadata["total_events"] == 3
    assert timeline.metadata["total_links"] > 0
    assert 0.0 <= timeline.metadata["confidence_avg"] <= 1.0
    assert timeline.metadata["strong_links"] >= 0
    assert timeline.metadata["medium_links"] >= 0
    assert timeline.metadata["weak_links"] >= 0
    assert timeline.metadata["conflicts"] >= 0

    # At least one strong or medium link should exist
    assert (
        timeline.metadata["strong_links"] + timeline.metadata["medium_links"]
    ) > 0


def test_causal_timeline_missing_layer3():
    """Validate that missing Layer3 returns None."""
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="missing_layer3",
            contentfingerprint="c" * 64,
            ingestiontimestamp=datetime.now(UTC),
            ingestionagent="test",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[ArtefatoBruto(id="art_1", tipo="original", uri="test.pdf")],
        ),
    )
    dm.layer2 = Layer2Evidence()
    # Deliberately omit Layer3

    timeline = build_causal_timeline_from_dm("missing_layer3", dm)
    assert timeline is None


def test_causal_timeline_missing_layer2():
    """Validate that missing Layer2 still returns timeline (empty grafo)."""
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="missing_layer2",
            contentfingerprint="d" * 64,
            ingestiontimestamp=datetime.now(UTC),
            ingestionagent="test",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[ArtefatoBruto(id="art_1", tipo="original", uri="test.pdf")],
        ),
    )
    # Deliberately omit Layer2
    dm.layer3 = Layer3Evidence(
        eventos_probatorios=[
            ProbatoryEvent(
                event_id="evt_x",
                event_type="teste",
                title="Evento de Teste",
                date_iso="2024-01-01T00:00:00Z",
                entities={},
                confidence=1.0,
            )
        ]
    )

    timeline = build_causal_timeline_from_dm("missing_layer2", dm)
    assert timeline is None  # No Layer2 means no causal links, so None


def test_causal_timeline_empty_grafo_graceful(dm_with_causal_links):
    """Validate graceful handling when no causal links exist."""
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid="empty_grafo",
            contentfingerprint="e" * 64,
            ingestiontimestamp=datetime.now(UTC),
            ingestionagent="test",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[ArtefatoBruto(id="art_1", tipo="original", uri="test.pdf")],
        ),
        layer2=Layer2Evidence(),
        layer3=Layer3Evidence(
            eventos_probatorios=[
                ProbatoryEvent(
                    event_id="evt_solo",
                    event_type="evento",
                    title="Single Event",
                    date_iso="2024-01-01T00:00:00Z",
                    entities={},
                    confidence=1.0,
                )
            ]
        ),
    )

    timeline = build_causal_timeline_from_dm("empty_grafo", dm)
    assert timeline is not None
    assert len(timeline.eventos) == 1
    assert len(timeline.grafo) == 0
    assert timeline.metadata["total_links"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
