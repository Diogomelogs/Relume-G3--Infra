"""
Golden Case: Eletricista com choque elétrico e síndrome fibromiálgica.

Documenta o caso real esperado do motor Kausal funcionando.
Teste de nexo causal previdenciário: acidente → lesão → agravamento → perícia.
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
from relluna.services.causal.engine import infer_causal_links, persist_causal_links_to_layer2


@pytest.fixture
def dm_eletricista_golden() -> DocumentMemory:
    """
    Cria DocumentMemory do golden case: eletricista com acidente elétrico.

    Documentos esperados:
    1. CAT (15/06/2024): "Acidente elétrico, queimadura 3º grau no braço"
    2. Atestado 1 (20/06/2024): "Queimadura, lesão muscular"
    3. Atestado 2 (15/07/2024): "Síndrome fibromiálgica, CID M79.7"
    4. Perícia INSS (30/08/2024): "Lesão compatível com acidente laboral"
    """
    doc_id = "golden_eletricista_001"

    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid=doc_id,
            contentfingerprint="a" * 64,
            ingestiontimestamp=datetime.now(UTC),
            ingestionagent="test_golden",
        ),
        layer1=Layer1Artefatos(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="artifact_001",
                    tipo="original",
                    uri=f"uploads/{doc_id}_artifact_001.pdf",
                    nome="CAT_acidente_eletrico.pdf",
                )
            ],
        ),
    )

    # Layer2: sinais determinísticos (apenas o que foi observado)
    dm.layer2 = Layer2Evidence()

    # Layer3: eventos probatórios (o que o sistema deduziu)
    dm.layer3 = Layer3Evidence(
        eventos_probatorios=[
            ProbatoryEvent(
                event_id="evt_001",
                event_type="acidente",
                title="Acidente Elétrico",
                description="Choque elétrico com queimadura 3º grau no braço direito",
                date_iso="2024-06-15T10:30:00Z",
                entities={"cid": "T20.0", "provider_activity": "eletricista"},
                confidence=1.0,  # Fato documentado
            ),
            ProbatoryEvent(
                event_id="evt_002",
                event_type="diagnostico",
                title="Lesão Muscular",
                description="Queimadura com lesão de tecido muscular",
                date_iso="2024-06-20T14:00:00Z",
                entities={"cid": "T21.0"},
                confidence=0.95,
            ),
            ProbatoryEvent(
                event_id="evt_003",
                event_type="diagnostico",
                title="Síndrome Fibromiálgica",
                description="Desenvolvimento de síndrome fibromiálgica pós-lesão",
                date_iso="2024-07-15T09:00:00Z",
                entities={"cid": "M79.7"},
                confidence=0.88,
            ),
            ProbatoryEvent(
                event_id="evt_004",
                event_type="perícia",
                title="Perícia INSS",
                description="Perícia médica que confirma nexo com acidente laboral",
                date_iso="2024-07-25T11:00:00Z",
                entities={"cid": "T20.0"},
                confidence=0.99,
            ),
        ]
    )

    return dm


def test_kausal_presuncao_ntep_eletricista(dm_eletricista_golden):
    """
    Valida que o motor Kausal identifica presunção NTEP:
    Eletricista + queimadura elétrica (T20) → Presunção legal.
    """
    links = infer_causal_links(dm_eletricista_golden)

    # Deve haver ligação entre evt_001 (acidente) e evt_002 (lesão)
    presuncao_link = next(
        (lnk for lnk in links if lnk.event_a_id == "evt_001" and lnk.event_b_id == "evt_002"),
        None,
    )

    assert presuncao_link is not None, "Deve haver presunção NTEP entre acidente e lesão"
    assert "presunção" in presuncao_link.link_type or "NTEP" in presuncao_link.rule_explanation
    assert presuncao_link.confidence >= 0.95, f"Confiança deve ser alta (é {presuncao_link.confidence})"
    assert "NTEP" in presuncao_link.rule_explanation or "tabela" in presuncao_link.rule_explanation.lower()


def test_kausal_progressao_anatomica_eletricista(dm_eletricista_golden):
    """
    Valida que o motor Kausal identifica progressão anatômica:
    Queimadura (T21) → Síndrome fibromiálgica (M79) = evolução de lesão.
    """
    links = infer_causal_links(dm_eletricista_golden)

    # Deve haver ligação entre evt_002 (lesão inicial) e evt_003 (agravamento)
    progressao_link = next(
        (lnk for lnk in links if lnk.event_a_id == "evt_002" and lnk.event_b_id == "evt_003"),
        None,
    )

    assert progressao_link is not None, "Deve haver progressão entre lesão inicial e agravamento"
    assert "progressão" in progressao_link.link_type or "anatomica" in progressao_link.link_type.lower()
    assert progressao_link.confidence >= 0.70, f"Confiança deve ser moderada (é {progressao_link.confidence})"


def test_kausal_pericia_confirma(dm_eletricista_golden):
    """
    Valida que perícia INSS posterior confirma o nexo da lesão original.
    """
    links = infer_causal_links(dm_eletricista_golden)

    # Deve haver ligação entre evt_001 (acidente) e evt_004 (perícia que confirma)
    # evt_004 tem CID T20.0 que corresponde a evt_001, não evt_002
    pericia_link = next(
        (lnk for lnk in links if lnk.event_a_id == "evt_001" and lnk.event_b_id == "evt_004"
         and "pericia" in lnk.rule_id.lower()),
        None,
    )

    assert pericia_link is not None, "Perícia deve confirmar lesão anterior"
    assert "pericia" in pericia_link.rule_id.lower() or "confirma" in pericia_link.rule_id.lower()
    assert pericia_link.confidence >= 0.80


def test_kausal_grafo_completo_eletricista(dm_eletricista_golden):
    """
    Valida o grafo causal completo do caso.

    Esperado:
    evt_001 (acidente) → evt_002 (lesão) → evt_003 (agravamento) → evt_004 (perícia)
    """
    links = infer_causal_links(dm_eletricista_golden)

    # Deve haver no mínimo 3 ligações (não contar conflitos)
    assert len(links) >= 3, f"Esperado ≥3 ligações, obteve {len(links)}"

    # Nenhuma ligação deve ser conflito
    conflitos = [lnk for lnk in links if lnk.is_conflict]
    assert len(conflitos) == 0, f"Não deve haver conflitos neste caso, encontrou {len(conflitos)}"

    # Todas as ligações devem ter confiança > 0.5
    assert all(lnk.confidence > 0.5 for lnk in links), "Todas as ligações devem ter confiança > 0.5"


def test_kausal_persistencia_em_layer2(dm_eletricista_golden):
    """
    Valida que os causal_links são persistidos corretamente em Layer2.sinais_documentais.
    """
    links = infer_causal_links(dm_eletricista_golden)
    dm = persist_causal_links_to_layer2(dm_eletricista_golden, links)

    assert "causal_link_v1" in dm.layer2.sinais_documentais
    sinal = dm.layer2.sinais_documentais["causal_link_v1"]
    assert sinal.valor is not None

    # Deserializar e validar
    import json

    links_json = json.loads(sinal.valor)
    assert len(links_json) == len(links), "JSON deve manter o mesmo número de ligações"
    assert all("event_a_id" in lnk for lnk in links_json), "Cada ligação deve ter event_a_id"


def test_kausal_visual_metadata_cores(dm_eletricista_golden):
    """
    Valida que cada ligação tem metadata visual (cor, espessura) para o frontend.
    """
    links = infer_causal_links(dm_eletricista_golden)

    for link in links:
        assert link.visual_color in [
            "#22c55e",  # verde (forte)
            "#f59e0b",  # amarelo (médio)
            "#6b7280",  # cinza (fraco)
            "#ef4444",  # vermelho (conflito)
        ], f"Cor inválida: {link.visual_color}"

        assert link.visual_thickness in [1, 2, 3], f"Espessura inválida: {link.visual_thickness}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
