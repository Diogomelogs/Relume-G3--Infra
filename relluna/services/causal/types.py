"""Tipos para análise de nexo causal (Kausal engine)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from relluna.core.document_memory import EvidenceRef


@dataclass
class CausalLink:
    """
    Aresta causal entre dois eventos probatórios.

    Representa a relação entre um evento anterior (causa) e um posterior (efeito),
    com evidência de nexo, confiança e rastreabilidade até a regra que a gerou.
    """

    # Identidades dos eventos ligados
    event_a_id: str
    event_b_id: str
    event_a_date: datetime
    event_b_date: datetime

    # Tipo de nexo (categoria da Lei 8.213/91)
    link_type: str  # "presuncao_legal" | "ntep" | "cronologia_reversibilidade" | "conflito"
    confidence: float  # 0.0-1.0

    # Rastreabilidade: qual regra disparou
    rule_id: str  # ex: "rule_presuncao_ntep"
    rule_explanation: str  # ex: "Operador de caixa + LER em NTEP"

    # Lastro: onde nos docs vieram os dados
    citations: List[EvidenceRef] = field(default_factory=list)

    # Anti-nexo: fatores que enfraquecem a tese causal
    weakening_factors: List[str] = field(default_factory=list)

    # Revisão humana
    review_state: str = "auto"  # "auto" | "needs_review" | "human_confirmed"
    review_note: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None

    @property
    def is_conflict(self) -> bool:
        """True se este nexo representa um conflito entre eventos."""
        return self.link_type == "conflito"

    @property
    def confidence_level(self) -> str:
        """Classifica confiança em níveis legíveis."""
        if self.confidence >= 0.9:
            return "forte"
        elif self.confidence >= 0.75:
            return "médio"
        elif self.confidence >= 0.5:
            return "fraco"
        return "rejeitado"

    @property
    def visual_color(self) -> str:
        """Cor para visualização no grafo."""
        if self.is_conflict:
            return "#ef4444"  # vermelho
        if self.confidence >= 0.9:
            return "#22c55e"  # verde
        elif self.confidence >= 0.75:
            return "#f59e0b"  # amarelo
        return "#6b7280"  # cinza

    @property
    def visual_thickness(self) -> int:
        """Espessura da seta para visualização."""
        if self.confidence >= 0.9:
            return 3
        elif self.confidence >= 0.75:
            return 2
        return 1


# Schema para validação em JSON (para sinais_documentais)
CAUSAL_LINK_V1_SCHEMA = {
    "type": "array",
    "description": "Grafo de nexos causais entre eventos",
    "items": {
        "type": "object",
        "properties": {
            "event_a_id": {"type": "string"},
            "event_b_id": {"type": "string"},
            "event_a_date": {"type": "string", "format": "date-time"},
            "event_b_date": {"type": "string", "format": "date-time"},
            "link_type": {
                "type": "string",
                "enum": ["presuncao_legal", "ntep", "cronologia_reversibilidade", "conflito"],
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "rule_id": {"type": "string"},
            "rule_explanation": {"type": "string"},
            "review_state": {
                "type": "string",
                "enum": ["auto", "needs_review", "human_confirmed"],
            },
        },
        "required": ["event_a_id", "event_b_id", "link_type", "confidence", "rule_id"],
    },
}
