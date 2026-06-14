"""
Regras de nexo causal previdenciário baseadas em Lei 8.213/91 + Decreto 3.048/99 + CEREST.

Cada regra é uma hipótese jurídica com base legal, confiança e explicação.
O sistema NUNCA inventa nexo; propõe baseado em legislação e jurisprudência.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from relluna.core.document_memory import EvidenceRef, ProbatoryEvent


@dataclass
class KausalRule:
    """Uma regra de nexo causal."""

    rule_id: str
    name: str
    description: str
    confidence_base: float  # 0.0-1.0, base antes de ajustes
    condition: Callable[[ProbatoryEvent, ProbatoryEvent, Dict[str, Any]], bool]
    explanation_template: str  # Template com placeholders
    legal_basis: str  # Lei/artigo que sustenta


# ─────────────────────────────────────────────────────────────────────────────
# REGRA 1: Presunção Legal NTEP
# ─────────────────────────────────────────────────────────────────────────────

NTEP_TABLE = {
    # (atividade, cid_prefix) → presunção
    ("operador_caixa", "M1"): True,  # LER / DORT em operador de caixa
    ("operador_caixa", "M2"): True,
    ("digitador", "M1"): True,  # LER / DORT em digitador
    ("digitador", "M2"): True,
    ("eletricista", "T20"): True,  # Queimadura elétrica (T20.0, T20.1, etc)
    ("eletricista", "T21"): True,  # Queimadura profunda (T21.0, T21.1, etc)
    ("eletricista", "T75"): True,  # Outros danos por corrente elétrica
    ("pintor", "J63"): True,  # Pneumoconiose (poeira)
    ("motorista", "S72"): True,  # Fratura em acidente de trabalho
    ("motorista", "S73"): True,
    ("pedreiro", "S72"): True,  # Queda em obra
    ("pedreiro", "S73"): True,
    ("agricultor", "W"): True,  # Acidente rural
}


def rule_presuncao_ntep(event_a: ProbatoryEvent, event_b: ProbatoryEvent, canonical: Dict[str, Any]) -> bool:
    """
    Presunção legal NTEP: doença ocupacional está na tabela para a atividade.

    Evento A = acidente/exposição
    Evento B = lesão/doença diagnosticada

    Lei 8.213/91 Art. 20: "Serão considerados como resultado do acidente da empresa
    as seguintes sequelas que evoluem para incapacidade parcial permanente: ..."
    """
    if not event_a.date_iso or not event_b.date_iso:
        return False

    date_a = datetime.fromisoformat(event_a.date_iso)
    date_b = datetime.fromisoformat(event_b.date_iso)

    # A deve vir antes de B
    if date_a >= date_b:
        return False

    # B deve ter CID
    cid_b = event_b.entities.get("cid", "")
    if not cid_b:
        return False

    # A pode ter atividade ou tipo
    atividade_a = event_a.entities.get("provider_activity", "").lower().replace(" ", "_")
    atividade_canonical = canonical.get("provider_activity", "").lower().replace(" ", "_")
    atividade = atividade_a or atividade_canonical

    if not atividade:
        return False

    cid_prefix_b = cid_b[:3] if len(cid_b) >= 3 else cid_b

    # Buscar na tabela NTEP (match flexível)
    for (act, cid_pref), has_presuncao in NTEP_TABLE.items():
        if has_presuncao and act in atividade and cid_pref in cid_prefix_b:
            return True

    return False


RULE_PRESUNCAO_NTEP = KausalRule(
    rule_id="rule_presuncao_ntep",
    name="Presunção Legal NTEP",
    description="Doença ocupacional listada na tabela CEREST/NTEP para a atividade",
    confidence_base=0.99,
    condition=rule_presuncao_ntep,
    explanation_template="Presunção legal: {atividade} + {cid} está na tabela NTEP (Lei 8.213/91 Art. 20)",
    legal_basis="Lei 8.213/1991 Art. 20; Decreto 3.048/1999; Tabela CEREST",
)


# ─────────────────────────────────────────────────────────────────────────────
# REGRA 2: Afastamento >30 dias após evento
# ─────────────────────────────────────────────────────────────────────────────


def rule_afastamento_prolongado(
    event_a: ProbatoryEvent, event_b: ProbatoryEvent, canonical: Dict[str, Any]
) -> bool:
    """
    Afastamento prolongado (>30 dias) após acidente indica nexo.

    Jurisprudência dominante (TNU): perda de capacidade = presunção de nexo.
    Se parou de trabalhar após evento, há evidência de nexo.
    """
    if not event_a.date_iso or not event_b.date_iso:
        return False

    date_a = datetime.fromisoformat(event_a.date_iso)
    date_b = datetime.fromisoformat(event_b.date_iso)

    # A antes de B
    if date_a >= date_b:
        return False

    # B é afastamento?
    if "afastamento" not in (event_b.event_type or "").lower():
        return False

    # Duração > 30 dias?
    dias = (date_b - date_a).days
    return dias > 30


RULE_AFASTAMENTO_PROLONGADO = KausalRule(
    rule_id="rule_afastamento_prolongado",
    name="Afastamento Prolongado (>30 dias)",
    description="Perda de capacidade/afastamento prolongado após acidente presume nexo",
    confidence_base=0.85,
    condition=rule_afastamento_prolongado,
    explanation_template="Afastamento de {dias} dias após acidente indica nexo causal (Jurisprudência TNU)",
    legal_basis="TNU; Jurisprudência dominante em benefícios previdenciários",
)


# ─────────────────────────────────────────────────────────────────────────────
# REGRA 3: Mesma CID em múltiplos documentos = validação
# ─────────────────────────────────────────────────────────────────────────────


def rule_mesmo_cid_multiplos_documentos(
    event_a: ProbatoryEvent, event_b: ProbatoryEvent, canonical: Dict[str, Any]
) -> bool:
    """
    Mesmo CID em eventos diferentes (ex: dois atestados com mesma lesão) validam continuidade.

    Não é nexo causal em si, é validação de que o diagnóstico é estável e real.
    """
    cid_a = event_a.entities.get("cid", "")
    cid_b = event_b.entities.get("cid", "")

    # Mesmo CID?
    if not cid_a or not cid_b:
        return False

    if cid_a[:3] != cid_b[:3]:  # Mesmo prefixo (ex: S72)
        return False

    # A antes de B
    if not event_a.date_iso or not event_b.date_iso:
        return False

    date_a = datetime.fromisoformat(event_a.date_iso)
    date_b = datetime.fromisoformat(event_b.date_iso)

    return date_a < date_b


RULE_MESMO_CID = KausalRule(
    rule_id="rule_mesmo_cid_multiplos_docs",
    name="Mesmo CID em Múltiplos Documentos",
    description="Diagnóstico estável (mesmo CID em documentos diferentes) valida continuidade",
    confidence_base=0.78,
    condition=rule_mesmo_cid_multiplos_documentos,
    explanation_template="CID {cid} confirmado em múltiplos documentos ({doc_a} e {doc_b}), validando diagnóstico",
    legal_basis="Princípio de coerência probatória",
)


# ─────────────────────────────────────────────────────────────────────────────
# REGRA 4: CIDs anatomicamente relacionados (progressão)
# ─────────────────────────────────────────────────────────────────────────────

ANATOMICAL_RELATIONSHIPS = {
    # (cid_a, cid_b) → True se B pode ser evolução de A
    ("S72", "S73"): True,  # Fratura → Luxação (mesmo osso)
    ("S73", "M17"): True,  # Luxação → Artrite
    ("T20", "L89"): True,  # Queimadura → Cicatriz (lesão de pele)
    ("T20", "M79"): True,  # Queimadura → Síndrome fibromiálgica (complicação)
    ("T21", "M79"): True,  # Queimadura profunda → Síndrome fibromiálgica
    ("M17", "M19"): True,  # Artrite leve → Artrite severa
    ("M65", "M67"): True,  # Tenossinovite → Artrite relacionada
}


def rule_progressao_anatomica(
    event_a: ProbatoryEvent, event_b: ProbatoryEvent, canonical: Dict[str, Any]
) -> bool:
    """
    CIDs anatomicamente relacionadas com cronologia = progressão de lesão.

    Lesão inicial (fratura) pode evoluir para complicações (artrite).
    Isso valida o nexo causal da lesão inicial.
    """
    cid_a = event_a.entities.get("cid", "")
    cid_b = event_b.entities.get("cid", "")

    if not cid_a or not cid_b:
        return False

    cid_a_prefix = cid_a[:3]
    cid_b_prefix = cid_b[:3]

    # Cronologia
    if not event_a.date_iso or not event_b.date_iso:
        return False

    date_a = datetime.fromisoformat(event_a.date_iso)
    date_b = datetime.fromisoformat(event_b.date_iso)

    if date_a >= date_b:
        return False

    # Relação anatômica?
    for (a, b), is_related in ANATOMICAL_RELATIONSHIPS.items():
        if cid_a_prefix == a and cid_b_prefix == b and is_related:
            return True

    return False


RULE_PROGRESSAO = KausalRule(
    rule_id="rule_progressao_anatomica",
    name="Progressão Anatômica",
    description="CIDs relacionadas anatomicamente em cronologia indicam progressão de lesão",
    confidence_base=0.82,
    condition=rule_progressao_anatomica,
    explanation_template="Progressão anatômica: {cid_a} (lesão inicial) → {cid_b} (complicação) indica nexo da lesão inicial",
    legal_basis="Critério médico-pericial: dose-resposta e progressão temporal",
)


# ─────────────────────────────────────────────────────────────────────────────
# REGRA 5: Conflito / Contra-nexo
# ─────────────────────────────────────────────────────────────────────────────


def rule_conflito_datas_cids(event_a: ProbatoryEvent, event_b: ProbatoryEvent, canonical: Dict[str, Any]) -> bool:
    """
    Conflito: a mesma lesão não pode ter datas muito diferentes nos documentos.

    Ex: "Atestado diz fratura fêmur em 20/01, mas raio-X de 15/01 não mostra fratura"
    = conflito que enfraquece o nexo.
    """
    if not event_a.date_iso or not event_b.date_iso:
        return False

    date_a = datetime.fromisoformat(event_a.date_iso)
    date_b = datetime.fromisoformat(event_b.date_iso)

    # Mesmo tipo de lesão (mesma CID)?
    cid_a = event_a.entities.get("cid", "")
    cid_b = event_b.entities.get("cid", "")

    if not cid_a or not cid_b:
        return False

    if cid_a[:3] != cid_b[:3]:  # CIDs diferentes
        return False

    # Mas datas muito diferentes (>60 dias) = conflito
    dias_diff = abs((date_b - date_a).days)
    return dias_diff > 60


RULE_CONFLITO = KausalRule(
    rule_id="rule_conflito_datas_cids",
    name="ALERTA: Conflito de Datas/CIDs",
    description="Mesmo diagnóstico com datas muito diferentes (>60 dias) indica conflito",
    confidence_base=0.0,  # Conflito reduz confiança
    condition=rule_conflito_datas_cids,
    explanation_template="⚠ CONFLITO: {cid} em {data_a} vs {data_b} (diferença: {dias} dias). Requer revisão.",
    legal_basis="Coerência probatória e análise de documentos contraditórios",
)


# ─────────────────────────────────────────────────────────────────────────────
# REGRA 6: Perícia confirma (força nexo anterior)
# ─────────────────────────────────────────────────────────────────────────────


def rule_pericia_confirma_anterior(
    event_a: ProbatoryEvent, event_b: ProbatoryEvent, canonical: Dict[str, Any]
) -> bool:
    """
    Perícia INSS posterior confirma diagnóstico anterior = força o nexo.

    Jurisprudência: Perícia contemporânea tem peso maior, mas perícia posterior que confirma
    também reforça.
    """
    if not event_a.date_iso or not event_b.date_iso:
        return False

    # B é perícia?
    if "perícia" not in (event_b.event_type or "").lower():
        return False

    # A antes de B
    date_a = datetime.fromisoformat(event_a.date_iso)
    date_b = datetime.fromisoformat(event_b.date_iso)

    if date_a >= date_b:
        return False

    # Mesmo CID (ou compatível)?
    cid_a = event_a.entities.get("cid", "")
    cid_b = event_b.entities.get("cid", "")

    if not cid_a or not cid_b:
        return False

    return cid_a[:3] == cid_b[:3]


RULE_PERICIA_CONFIRMA = KausalRule(
    rule_id="rule_pericia_confirma_anterior",
    name="Perícia Confirma Diagnóstico Anterior",
    description="Perícia INSS que confirma diagnóstico anterior reforça o nexo",
    confidence_base=0.88,
    condition=rule_pericia_confirma_anterior,
    explanation_template="Perícia INSS (data: {data_pericia}) confirma {cid} diagnosticado anteriormente, reforçando nexo causal",
    legal_basis="Jurisprudência STJ: peso probatório da perícia em benefícios previdenciários",
)


# ─────────────────────────────────────────────────────────────────────────────
# COMPILAÇÃO DAS REGRAS
# ─────────────────────────────────────────────────────────────────────────────

KAUSAL_RULES: List[KausalRule] = [
    RULE_PRESUNCAO_NTEP,
    RULE_AFASTAMENTO_PROLONGADO,
    RULE_MESMO_CID,
    RULE_PROGRESSAO,
    RULE_CONFLITO,
    RULE_PERICIA_CONFIRMA,
]

__all__ = [
    "KAUSAL_RULES",
    "KausalRule",
    "NTEP_TABLE",
    "ANATOMICAL_RELATIONSHIPS",
]
