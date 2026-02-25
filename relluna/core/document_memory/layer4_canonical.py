from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, AliasChoices

class EntidadeCanonica(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    label: str

class Layer4SemanticNormalization(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )

    # Aceita: data_canonica, date_canonical, datacanonica
    data_canonica: Optional[Union[datetime, str]] = Field(
        default=None,
        validation_alias=AliasChoices("data_canonica", "date_canonical", "datacanonica"),
        serialization_alias="data_canonica",
    )

    # Aceita: periodo, period_label
    periodo: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("periodo", "period_label"),
        serialization_alias="periodo",
    )

    # NOVO: local canônico (aceita localcanonico legado)
    local_canonico: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("local_canonico", "localcanonico"),
        serialization_alias="local_canonico",
    )

    # Aceita: entidades, entities, pessoasentidades (legado)
    entidades: List[EntidadeCanonica] = Field(
        default_factory=list,
        validation_alias=AliasChoices("entidades", "entities", "pessoasentidades"),
        serialization_alias="entidades",
    )

    # Aceita: tags e temas (legado)
    tags: List[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("tags", "temas"),
        serialization_alias="tags",
    )

    # NOVO: relações temporais (aceita relacoestemporais legado)
    relacoes_temporais: List[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("relacoes_temporais", "relacoestemporais"),
        serialization_alias="relacoes_temporais",
    )

    @property
    def rotulo_temporal(self) -> Optional[str]:
        return self.periodo