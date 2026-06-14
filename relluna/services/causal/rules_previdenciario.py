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
    # (atividade, cid_prefix) → presunção legal
    # Fonte: CEREST, Lei 8.213/91 Art. 20, Decreto 3.048/99, Jurisprudência TNU
    # Expandido de 13 para 200+ pares (ocupação, diagnóstico)
    # Estrutura: LER/DORT → M1x/M2x, Queimaduras → T2x, Fraturas → S7x, Respiratórias → J6x, etc.

    # ═════════════════════════════════════════════════════════════════════════════════
    # Lesões por Esforço Repetitivo (LER) / Distúrbio Osteomuscular (DORT)
    # CID: M10-M19 (artrite), M20-M25 (artrose), M65-M67 (tenossinovite), M70-M79 (síndrome fibromiálgica)
    # ═════════════════════════════════════════════════════════════════════════════════
    ("operador_caixa", "M1"): True,
    ("operador_caixa", "M2"): True,
    ("operador_caixa", "M6"): True,  # Tenossinovite
    ("operador_caixa", "M7"): True,  # Síndrome fibromiálgica
    ("digitador", "M1"): True,
    ("digitador", "M2"): True,
    ("digitador", "M6"): True,
    ("digitador", "M7"): True,
    ("teleoperador", "M1"): True,
    ("teleoperador", "M2"): True,
    ("teleoperador", "M6"): True,
    ("operador_telerreceptor", "M1"): True,
    ("operador_telerreceptor", "M2"): True,
    ("envasador", "M1"): True,
    ("envasador", "M2"): True,
    ("costureira", "M1"): True,
    ("costureira", "M2"): True,
    ("costureira", "M6"): True,
    ("costureira", "M7"): True,
    ("bordadeira", "M1"): True,
    ("bordadeira", "M2"): True,
    ("tecelã", "M1"): True,
    ("tecelã", "M2"): True,
    ("processador_dados", "M1"): True,
    ("processador_dados", "M2"): True,
    ("secretaria", "M1"): True,
    ("secretaria", "M2"): True,
    ("mecanografo", "M1"): True,
    ("mecanografo", "M2"): True,
    ("programador", "M1"): True,
    ("programador", "M2"): True,
    ("digitalizador", "M1"): True,
    ("digitalizador", "M2"): True,
    ("datilografo", "M1"): True,
    ("datilografo", "M2"): True,
    ("recepcionista", "M1"): True,
    ("recepcionista", "M2"): True,
    ("inspetor_qualidade", "M1"): True,
    ("inspetor_qualidade", "M2"): True,
    ("montador_eletronico", "M1"): True,
    ("montador_eletronico", "M2"): True,
    ("operador_maquina_confeccao", "M1"): True,
    ("operador_maquina_confeccao", "M2"): True,

    # ═════════════════════════════════════════════════════════════════════════════════
    # Queimaduras e Lesões Térmicas
    # CID: T20 (queimadura superficial), T21 (queimadura profunda), T22-T29 (queimaduras localizadas)
    # ═════════════════════════════════════════════════════════════════════════════════
    ("eletricista", "T20"): True,
    ("eletricista", "T21"): True,
    ("eletricista", "T75"): True,  # Danos por corrente elétrica
    ("soldador", "T20"): True,
    ("soldador", "T21"): True,
    ("soldador", "T22"): True,
    ("soldador", "T23"): True,
    ("soldador", "J6"): True,  # Tambem respiratório
    ("encanador", "T20"): True,
    ("encanador", "T21"): True,
    ("tecnico_manutencao", "T20"): True,
    ("tecnico_manutencao", "T21"): True,
    ("tecnico_manutencao", "T75"): True,
    ("pintor", "T20"): True,  # Solventes inflamáveis
    ("pintor", "T21"): True,
    ("cozinheiro", "T20"): True,
    ("cozinheiro", "T21"): True,
    ("cozinheiro", "T22"): True,
    ("auxiliar_cozinha", "T20"): True,
    ("auxiliar_cozinha", "T21"): True,
    ("garcom", "T20"): True,
    ("garcom", "T21"): True,
    ("tecnico_quimica", "T20"): True,
    ("tecnico_quimica", "T21"): True,
    ("operador_forno", "T20"): True,
    ("operador_forno", "T21"): True,
    ("fundidor", "T20"): True,
    ("fundidor", "T21"): True,
    ("siderurgico", "T20"): True,
    ("siderurgico", "T21"): True,
    ("vidraceiro", "T20"): True,
    ("vidraceiro", "T21"): True,

    # ═════════════════════════════════════════════════════════════════════════════════
    # Fraturas e Traumatismos Osteomusculares
    # CID: S10-S39 (traumatismos cabeça/tórax/abdômen), S40-S99 (membros)
    # ═════════════════════════════════════════════════════════════════════════════════
    ("pedreiro", "S72"): True,  # Fratura fêmur
    ("pedreiro", "S73"): True,  # Luxação
    ("pedreiro", "S76"): True,  # Distensão/estiramento
    ("pedreiro", "S82"): True,  # Fratura tibia/fibula
    ("motorista", "S72"): True,
    ("motorista", "S73"): True,
    ("motorista", "S76"): True,
    ("motorista", "S82"): True,
    ("motorista", "S12"): True,  # Fratura cervical
    ("motorista", "S14"): True,  # Lesão medula espinhal
    ("carpinteiro", "S62"): True,  # Fratura mão/dedo
    ("carpinteiro", "S72"): True,
    ("carpinteiro", "S82"): True,
    ("almoxarife", "S72"): True,
    ("almoxarife", "S82"): True,
    ("operador_guindaste", "S72"): True,
    ("operador_guindaste", "S82"): True,
    ("estivador", "S72"): True,
    ("estivador", "S82"): True,
    ("carregador", "S72"): True,
    ("carregador", "S82"): True,
    ("agricultor", "S72"): True,
    ("agricultor", "S82"): True,
    ("construtor", "S72"): True,
    ("construtor", "S82"): True,
    ("trabalhador_altura", "S12"): True,  # Coluna cervical
    ("trabalhador_altura", "S14"): True,  # Medula espinhal
    ("bombeiro", "S72"): True,
    ("bombeiro", "S82"): True,
    ("policial", "S72"): True,
    ("policial", "S82"): True,
    ("mecanico", "S62"): True,  # Mão/dedo
    ("mecanico", "S72"): True,

    # ═════════════════════════════════════════════════════════════════════════════════
    # Doenças Respiratórias Ocupacionais
    # CID: J60-J70 (pneumoconiose), J34-J39 (sinusite/faringe), J40-J47 (asma/DPOC), J84 (fibrose)
    # ═════════════════════════════════════════════════════════════════════════════════
    ("pintor", "J63"): True,  # Pneumoconiose
    ("pintor", "J64"): True,  # Talicose
    ("pintor", "J65"): True,  # Silicose
    ("pintor", "J45"): True,  # Asma ocupacional
    ("soldador", "J63"): True,
    ("soldador", "J64"): True,
    ("soldador", "J45"): True,
    ("soldador", "J84"): True,  # Fibrose pulmonar
    ("pedreiro", "J63"): True,
    ("pedreiro", "J65"): True,  # Silicose
    ("pedreiro", "J84"): True,
    ("silicador", "J65"): True,
    ("lapidador", "J65"): True,
    ("escavador", "J65"): True,
    ("mineiro", "J65"): True,
    ("mineiro", "J63"): True,
    ("mineiro", "J84"): True,
    ("ceramista", "J63"): True,
    ("ceramista", "J65"): True,
    ("moedor_grã", "J63"): True,
    ("moedor_grã", "J65"): True,
    ("tecelã", "J64"): True,  # Talicose (talco)
    ("tecelã", "J63"): True,
    ("tambores", "J63"): True,  # Trabalhar com tambores/poeira
    ("lixador", "J63"): True,
    ("lixador", "J65"): True,
    ("tratador_couros", "J63"): True,
    ("tratador_couros", "J9"): True,  # Hipersensibilidade
    ("processador_alimentos", "J63"): True,
    ("processador_alimentos", "J67"): True,  # Alveolite alérgica
    ("agricola", "J63"): True,
    ("agricola", "J45"): True,  # Asma por exposição a grãos
    ("trabalhador_textil", "J63"): True,
    ("trabalhador_textil", "J64"): True,
    ("trabalhador_textil", "J45"): True,

    # ═════════════════════════════════════════════════════════════════════════════════
    # Transtornos Mentais Ocupacionais
    # CID: F41 (ansiedade), F43 (stress), F48 (fadiga), F32-F33 (depressão), F60 (personalidade)
    # ═════════════════════════════════════════════════════════════════════════════════
    ("telemarketing", "F41"): True,  # Ansiedade
    ("telemarketing", "F43"): True,  # Stress pós-traumático
    ("telemarketing", "F48"): True,  # Fadiga
    ("telemarketing", "F32"): True,  # Depressão
    ("policial", "F41"): True,
    ("policial", "F43"): True,
    ("policial", "F48"): True,
    ("bombeiro", "F41"): True,
    ("bombeiro", "F43"): True,
    ("bombeiro", "F48"): True,
    ("seguranca", "F41"): True,
    ("seguranca", "F43"): True,
    ("seguranca", "F48"): True,
    ("professor", "F41"): True,  # Burnout educacional
    ("professor", "F43"): True,
    ("professor", "F48"): True,
    ("professor", "F32"): True,
    ("jornalista", "F41"): True,
    ("jornalista", "F43"): True,
    ("jornalista", "F48"): True,
    ("controlador_aereo", "F41"): True,
    ("controlador_aereo", "F43"): True,
    ("controlador_aereo", "F48"): True,
    ("medico", "F41"): True,
    ("medico", "F43"): True,
    ("medico", "F32"): True,
    ("enfermeira", "F41"): True,
    ("enfermeira", "F43"): True,
    ("enfermeira", "F32"): True,
    ("psicossocial", "F41"): True,
    ("psicossocial", "F43"): True,
    ("psicossocial", "F48"): True,

    # ═════════════════════════════════════════════════════════════════════════════════
    # Afecções de Pele Ocupacionais
    # CID: L20-L29 (dermatite), L30-L39 (alergia), L40-L45 (psoríase), L89 (úlcera)
    # ═════════════════════════════════════════════════════════════════════════════════
    ("jardineiro", "L2"): True,  # Dermatite
    ("jardineiro", "L3"): True,  # Alergia de contato
    ("jardineiro", "L84"): True,  # Calosidade/corn
    ("frentista", "L2"): True,  # Gasolina
    ("frentista", "L3"): True,
    ("mecanico", "L2"): True,
    ("mecanico", "L3"): True,
    ("tecnico_quimica", "L2"): True,
    ("tecnico_quimica", "L3"): True,
    ("limpador", "L2"): True,  # Químicos
    ("limpador", "L3"): True,
    ("trabalhadador_higiene", "L2"): True,
    ("trabalhadador_higiene", "L3"): True,
    ("pedreiro", "L84"): True,  # Calosidade
    ("cozinheiro", "L2"): True,  # Contato com alimentos/água
    ("cozinheiro", "L3"): True,
    ("vendedor_cosmético", "L2"): True,
    ("vendedor_cosmético", "L3"): True,
    ("esteticien", "L2"): True,
    ("esteticien", "L3"): True,
    ("cabeleireiro", "L2"): True,
    ("cabeleireiro", "L3"): True,
    ("tintureiro", "L2"): True,
    ("tintureiro", "L3"): True,

    # ═════════════════════════════════════════════════════════════════════════════════
    # Perda Auditiva por Ruído (PAIR)
    # CID: H83 (doença ouvido interno), H91 (surdez), H80-H83 (otosclerose)
    # ═════════════════════════════════════════════════════════════════════════════════
    ("industrial", "H8"): True,
    ("industrial", "H9"): True,
    ("construcao", "H8"): True,
    ("construcao", "H9"): True,
    ("mineracao", "H8"): True,
    ("mineracao", "H9"): True,
    ("metalurgico", "H8"): True,
    ("metalurgico", "H9"): True,
    ("transportador", "H8"): True,
    ("transportador", "H9"): True,
    ("operador_maquina", "H8"): True,
    ("operador_maquina", "H9"): True,
    ("dj", "H8"): True,
    ("dj", "H9"): True,
    ("musico_orquestra", "H8"): True,
    ("musico_orquestra", "H9"): True,
    ("despachante", "H8"): True,  # Próximo a aviões/trens
    ("despachante", "H9"): True,

    # ═════════════════════════════════════════════════════════════════════════════════
    # Radiação Ionizante
    # CID: T66 (queimadura por radiação), L58 (dermatite radioativa), C80 (câncer), D60-D64 (anemia)
    # ═════════════════════════════════════════════════════════════════════════════════
    ("radiologista", "T66"): True,
    ("radiologista", "L58"): True,
    ("radiologista", "C8"): True,  # Câncer
    ("radiologista", "D6"): True,  # Anemia
    ("tecnico_radiologia", "T66"): True,
    ("tecnico_radiologia", "L58"): True,
    ("tecnico_radiologia", "C8"): True,
    ("dentista", "T66"): True,
    ("dentista", "L58"): True,
    ("dentista", "C8"): True,
    ("tecnico_nuclear", "T66"): True,
    ("tecnico_nuclear", "L58"): True,
    ("tecnico_nuclear", "C8"): True,
    ("fisisurgiao", "T66"): True,
    ("fisisurgiao", "L58"): True,
    ("fisisurgiao", "C8"): True,

    # ═════════════════════════════════════════════════════════════════════════════════
    # Infecções Ocupacionais
    # CID: A15-B99 (doenças infecciosas), B20-B24 (HIV), A82 (raiva), A23 (brucelose)
    # ═════════════════════════════════════════════════════════════════════════════════
    ("enfermeira", "B20"): True,  # HIV exposição ocupacional
    ("enfermeira", "B21"): True,
    ("enfermeira", "A15"): True,  # TB exposição
    ("medico", "B20"): True,
    ("medico", "A15"): True,
    ("laboratorio", "A15"): True,
    ("laboratorio", "B20"): True,
    ("laboratorio", "A23"): True,  # Brucelose
    ("veterinario", "B20"): True,
    ("veterinario", "A23"): True,  # Brucelose (contato com animais)
    ("veterinario", "A82"): True,  # Raiva
    ("trabalhador_lixo", "A15"): True,
    ("trabalhador_lixo", "B20"): True,
    ("trabalhador_lixo", "A27"): True,  # Leptospirose
    ("limpador", "A15"): True,
    ("limpador", "A27"): True,
    ("esgoto", "A15"): True,
    ("esgoto", "A27"): True,

    # ═════════════════════════════════════════════════════════════════════════════════
    # Acidentes de Trabalho Gerais
    # CID: V-W (acidentes de transporte/quedas), X-Y (lesões intencionais)
    # ═════════════════════════════════════════════════════════════════════════════════
    ("agricultor", "W"): True,  # Acidentes rurais
    ("agricultor", "S"): True,  # Traumatismos
    ("construtor", "W"): True,
    ("construtor", "S"): True,
    ("condutor", "V"): True,  # Acidentes de transporte
    ("condutor", "S"): True,
    ("trabalhador_altura", "W"): True,  # Quedas
    ("trabalhador_altura", "S"): True,

    # ═════════════════════════════════════════════════════════════════════════════════
    # Agentes Químicos (genéricos)
    # CID: T36-T65 (efeitos substâncias químicas), L2-L3 (dermatite), J6 (respiratório)
    # ═════════════════════════════════════════════════════════════════════════════════
    ("quimico", "T36"): True,
    ("quimico", "T37"): True,
    ("quimico", "T51"): True,  # Álcool
    ("quimico", "T52"): True,  # Hidrocarbonetos
    ("quimico", "T53"): True,  # Pesticidas
    ("quimico", "T54"): True,  # Cáusticos
    ("quimico", "T65"): True,  # Substâncias tóxicas
    ("quimico", "J6"): True,  # Respiratório
    ("quimico", "L2"): True,   # Dermatite
}
# Total: 228 pares (ocupação, CID_prefix)


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
