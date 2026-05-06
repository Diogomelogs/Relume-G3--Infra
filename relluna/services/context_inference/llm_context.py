from __future__ import annotations

from typing import Any

from relluna.core.document_memory import (
    DocumentMemory,
    Layer3Evidence,
    SemanticEntity,
    TemporalReference,
)
from relluna.core.document_memory.types_basic import EvidenceRef, InferenceMeta, InferredDatetime, InferredString
from relluna.infra.azure_openai.client import chat_json

_SOURCE = "azure_openai"
_METHOD = "llm.json_schema"

# Regras: LLM só pode usar evidências vindas da Layer2.
# Lastro: referenciar campos de Layer2 por "path" (ex: "layer2.data_exif", "layer2.texto_ocr_literal").
def _evidence_ref(path: str) -> EvidenceRef:
    return EvidenceRef(path=path)

def infer_layer3_from_layer2(dm: DocumentMemory) -> Layer3Evidence:
    l2 = dm.layer2.model_dump()

    # input mínimo e auditável
    evidence = {
        "media": str(dm.layer1.midia),
        "origin": str(dm.layer1.origem),
        "layer2": l2,
    }

    schema = {
        "type": "object",
        "properties": {
            "tipo_documento": {"type": ["string", "null"]},
            "temporalidades": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tipo": {"type": "string"},
                        "inicio_iso": {"type": ["string", "null"]},
                        "fim_iso": {"type": ["string", "null"]},
                        "confianca": {"type": ["number", "null"]},
                        "lastro_paths": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["tipo", "inicio_iso", "fim_iso", "confianca", "lastro_paths"],
                },
            },
            "entidades": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tipo": {"type": "string"},
                        "valor": {"type": "string"},
                        "score": {"type": ["number", "null"]},
                        "lastro_paths": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["tipo", "valor", "score", "lastro_paths"],
                },
            },
            "regras_aplicadas": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["tipo_documento", "temporalidades", "entidades", "regras_aplicadas"],
        "additionalProperties": False,
    }

    system = (
        "Você é um motor de inferência rastreável da Relluna.\n"
        "Regras:\n"
        "1) Não invente fatos. Se não houver evidência, retorne null/[].\n"
        "2) Toda inferência deve citar lastro_paths apontando para campos da layer2.\n"
        "3) Saída DEVE respeitar o JSON schema fornecido.\n"
    )

    user = {
        "instruction": "Inferir Layer3 a partir da Layer2, com rastreabilidade.",
        "evidence": evidence,
        "output_json_schema": schema,
    }

    try:
        out: dict[str, Any] = chat_json(system=system, user_json=user, json_schema=schema)
    except RuntimeError as e:
        # Fallback controlado quando não há chave Azure em ambiente de teste/desenv.
        msg = str(e)
        if "Missing env var: AZURE_OPENAI_API_KEY" in msg:
            out = {
                "tipo_documento": None,
                "temporalidades": [],
                "entidades": [],
                "regras_aplicadas": ["llm_offline_missing_api_key"],
            }
        else:
            # Qualquer outro erro de runtime continua sendo fatal (problema real de infra).
            raise

    meta = InferenceMeta(engine=_SOURCE, method=_METHOD)

    l3 = Layer3Evidence()

    # tipo_documento
    if out.get("tipo_documento"):
        l3.tipo_documento = InferredString(
            valor=out["tipo_documento"],
            fonte=_SOURCE,
            metodo=_METHOD,
            estado="inferido",
            confianca=0.6,
            lastro=[_evidence_ref(p) for p in (out.get("temporalidades", [])[:0] or [])],  # mantém vazio; lastro real via entidades/temporal
            meta=meta,
        )

    # temporalidades
    for t in out.get("temporalidades", []):
        lastro = [_evidence_ref(p) for p in t.get("lastro_paths", [])]
        l3.temporalidades_inferidas.append(
            TemporalReference(
                tipo=t["tipo"],
                inicio=InferredDatetime(valor=t["inicio_iso"]) if t["inicio_iso"] else None,
                fim=InferredDatetime(valor=t["fim_iso"]) if t["fim_iso"] else None,
                confianca=t.get("confianca"),
                lastro=lastro,
                meta=meta,
            )
        )

    # entidades
    for e in out.get("entidades", []):
        lastro = [_evidence_ref(p) for p in e.get("lastro_paths", [])]
        l3.entidades_semanticas.append(
            SemanticEntity(
                tipo=e["tipo"],
                valor=e["valor"],
                score=e.get("score"),
                lastro=lastro,
                meta=meta,
            )
        )

    l3.regras_aplicadas = out.get("regras_aplicadas", [])
    return l3
