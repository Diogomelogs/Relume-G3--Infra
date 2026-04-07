from __future__ import annotations

from typing import Any, Dict, List, Tuple


def classify_page_subtype(page_text: str) -> Dict[str, Any]:
    t = (page_text or "").lower()

    scores: List[Tuple[str, int]] = []

    rule_map = {
        "atestado_medico": [
            "atestado",
            "declaro para devidos fins",
            "afastado(a)",
            "afastado",
            "internado(a)",
            "internado",
            "diagnostico",
            "diagnóstico",
            "cid",
        ],
        "notificacao_receita": [
            "notificacao de receita",
            "medicamentos ou substancias",
            "identificacao do emitente",
        ],
        "receituario": [
            "receituario",
            "receituário",
            "orientacao ao paciente",
            "orientação ao paciente",
            "retencao da farmacia",
            "retenção da farmácia",
            "comprimido",
            "posologia",
        ],
        "registro_atendimento": [
            "data/hora atendimento",
            "prestador",
            "servico",
            "serviço",
            "convenio",
            "convênio",
            "internacao",
            "internação",
        ],
        "cabecalho_hospitalar": [
            "hospital das clinicas",
            "hospital das clínicas",
            "faculdade de medicina",
            "fmusp",
            "hospital santa isabel",
        ],
        "formulario_administrativo": [
            "identificacao do comprador",
            "identificação do comprador",
            "carimbo do fornecedor",
            "nome do vendedor",
        ],
        "laudo_medico": [
            "laudo",
            "impressao diagnostica",
            "impressão diagnóstica",
            "exame",
            "ressonancia",
            "ressonância",
            "tomografia",
            "radiografia",
        ],
        "documento_previdenciario": [
            "beneficio",
            "benefício",
            "nb",
            "dib",
            "indeferimento",
            "carta de concessao",
            "carta de concessão",
        ],
    }

    for subtype, keys in rule_map.items():
        score = sum(1 for k in keys if k in t)
        scores.append((subtype, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    best_subtype, best_score = scores[0]

    active_subtypes = [sub for sub, score in scores if score >= 2]

    if len(active_subtypes) >= 2:
        value = "documento_composto"
        confidence = 0.92
        components = active_subtypes
    elif best_score >= 2:
        value = best_subtype
        confidence = min(0.70 + 0.08 * best_score, 0.95)
        components = [best_subtype]
    elif any(k in t for k in ["crm", "paciente", "hospital", "receituario", "receituário", "atestado"]):
        value = "documento_medico"
        confidence = 0.55
        components = ["documento_medico"]
    else:
        value = "unknown"
        confidence = 0.20
        components = []

    expected_roles = {
        "patient": 1 if value in {"atestado_medico", "receituario", "registro_atendimento", "laudo_medico", "documento_medico"} else 0,
        "mother": "optional",
        "provider": 1 if value in {"atestado_medico", "receituario", "registro_atendimento", "laudo_medico", "documento_medico"} else "optional",
        "organization": 1 if value in {"atestado_medico", "registro_atendimento", "laudo_medico", "cabecalho_hospitalar", "documento_medico"} else "optional",
    }

    document_semantics = {
        "has_clinical_statement": value in {"atestado_medico", "registro_atendimento", "laudo_medico", "documento_medico"},
        "has_signature_block": value in {"atestado_medico", "receituario", "laudo_medico", "documento_medico"},
        "has_attendance_or_leave_dates": value in {"atestado_medico", "registro_atendimento"},
    }

    return {
        "value": value,
        "confidence": confidence,
        "components": components,
        "expected_roles": expected_roles,
        "document_semantics": document_semantics,
    }