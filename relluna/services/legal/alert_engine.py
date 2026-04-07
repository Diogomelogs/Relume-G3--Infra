from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from relluna.domain.legal_fields import CanonicalExtraction, LegalAlert


def _field_map(extractions: List[CanonicalExtraction]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for ext in extractions:
        row = {"doc_type": ext.doc_type}
        for f in ext.fields:
            row[f.name] = f.value
        out.setdefault(ext.doc_type, []).append(row)
    return out


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            continue
    return None


def _has_doc(rows: Dict[str, List[Dict[str, Any]]], doc_type: str) -> bool:
    return bool(rows.get(doc_type))


def _contains_any(text: str, terms: List[str]) -> bool:
    t = (text or "").lower()
    return any(term.lower() in t for term in terms)


def evaluate_alerts(extractions: List[CanonicalExtraction], today: Optional[datetime] = None) -> List[LegalAlert]:
    today = today or datetime.utcnow()
    rows = _field_map(extractions)
    alerts: List[LegalAlert] = []

    # Lógica 1
    for trct in rows.get("TRAB_TRCT", []):
        dem = _parse_date(trct.get("Data_Demissao"))
        if dem and dem < (today - timedelta(days=730)):
            for concessao in rows.get("PREV_CARTA_CONCESSAO", []):
                if str(concessao.get("Especie_Beneficio") or "").upper() == "B92":
                    alerts.append(
                        LegalAlert(
                            code="ALERTA_PRESCRICAO_SUSPENSAO_B92",
                            title="Contrato Suspenso por B92",
                            severity="alta",
                            message="Contrato suspenso por B92. Prescrição conta a partir da concessão do benefício.",
                            supporting_facts=[trct, concessao],
                        )
                    )

    # Lógica 2
    for prev in rows.get("PREV_CARTA_CONCESSAO", []) + rows.get("PREV_LAUDO_SABI", []):
        dcb = _parse_date(prev.get("DCB"))
        if not dcb:
            continue
        for aso in rows.get("SST_ASO_RETORNO", []):
            data_aso = _parse_date(aso.get("Data_ASO"))
            if data_aso and data_aso >= dcb and str(aso.get("Resultado_ASO") or "").lower() == "inapto":
                alerts.append(
                    LegalAlert(
                        code="ALERTA_LIMBO_PREVIDENCIARIO",
                        title="Limbo Previdenciário Identificado",
                        severity="alta",
                        message="INSS deu alta, empresa recusou retorno.",
                        supporting_facts=[prev, aso],
                    )
                )

    # Lógica 3
    exames = rows.get("MED_EXAME_IMAGEM", [])
    admissoes = rows.get("TRAB_CTPS", []) + rows.get("TRAB_FICHA_REGISTRO", [])
    has_aet = _has_doc(rows, "SST_AET")
    adm_date = None
    for d in admissoes:
        adm_date = _parse_date(d.get("Data_Admissao")) or adm_date

    preexist = None
    posterior_grave = None
    for ex in exames:
        dt = _parse_date(ex.get("Data_Documento"))
        concl = str(ex.get("Conclusao_Exame") or "").lower()
        if adm_date and dt and dt < adm_date and "degenerativo" in concl:
            preexist = ex
        if adm_date and dt and dt >= adm_date and any(term in concl for term in ["grave", "incapacitante", "extrusão discal", "extrusao discal"]):
            posterior_grave = ex

    if preexist and posterior_grave and not has_aet:
        alerts.append(
            LegalAlert(
                code="ALERTA_CONCAUSA_AGRAVAMENTO",
                title="Possível Concausa",
                severity="alta",
                message="Doença preexistente agravada. Falta de Análise Ergonômica (AET) na documentação.",
                supporting_facts=[preexist, posterior_grave],
            )
        )

    # Lógica 4
    h90_present = any(
        str(a.get("CID_Atestado") or "").upper().startswith("H90")
        for a in rows.get("MED_ATESTADO", []) + rows.get("MED_AUDIOMETRIA", [])
    )
    if h90_present:
        epi_rows = rows.get("SST_FICHA_EPI", [])
        irregular = False
        if not epi_rows:
            irregular = True
        else:
            dates = sorted(filter(None, [_parse_date(e.get("Data_Entrega_EPI")) for e in epi_rows]))
            if any(not e.get("Numero_CA_EPI") for e in epi_rows):
                irregular = True
            for i in range(1, len(dates)):
                if (dates[i] - dates[i - 1]).days > 180:
                    irregular = True
        if irregular:
            alerts.append(
                LegalAlert(
                    code="ALERTA_EPI_IRREGULAR",
                    title="Ineficácia / irregularidade de EPI",
                    severity="alta",
                    message="EPI documentado de forma irregular. Forte tese para afastar neutralização do ruído.",
                    supporting_facts=epi_rows,
                )
            )

    # Lógica 5
    has_b31 = any(str(c.get("Especie_Beneficio") or "").upper() == "B31" for c in rows.get("PREV_CARTA_CONCESSAO", []))
    psych_present = any(
        any(str(a.get("CID_Atestado") or "").upper().startswith(prefix) for prefix in ["F32", "F41", "Z73"])
        for a in rows.get("MED_ATESTADO", [])
    )
    pcmsos = rows.get("SST_PCMSO", [])
    if has_b31 and psych_present:
        mentions_psych = any("psicossoc" in str(p).lower() for p in pcmsos)
        if not mentions_psych:
            alerts.append(
                LegalAlert(
                    code="ALERTA_CONFLITO_NEXO_B31",
                    title="Conflito de Nexo",
                    severity="alta",
                    message="INSS não reconheceu acidente, mas há indícios de omissão no PCMSO patronal.",
                    supporting_facts=rows.get("PREV_CARTA_CONCESSAO", []) + rows.get("MED_ATESTADO", []) + pcmsos,
                )
            )

    # Lógica 6
    sem_vinculo = not _has_doc(rows, "TRAB_CTPS")
    sem_cnis = _has_doc(rows, "PREV_CNIS")
    has_loas = any(str(c.get("Especie_Beneficio") or "").upper() in {"B87", "LOAS"} for c in rows.get("PREV_CARTA_CONCESSAO", []))
    exposicao = False
    for med in rows.get("MED_LAUDO_ASSISTENTE_TECNICO", []) + rows.get("MED_PRONTUARIO_CLINICO", []) + rows.get("MED_EXAME_IMAGEM", []):
        txt = str(med)
        if _contains_any(txt, ["agrotóxicos", "agrotoxicos", "exposição", "silica", "ruído", "ruido"]):
            exposicao = True
            break
    if sem_vinculo and sem_cnis and has_loas and exposicao:
        alerts.append(
            LegalAlert(
                code="ALERTA_LOAS_TRABALHO_INFORMAL",
                title="LOAS x Doença Ocupacional",
                severity="alta",
                message="Trabalho informal. Recebimento de LOAS por culpa patronal na sonegação previdenciária.",
                supporting_facts=rows.get("PREV_CARTA_CONCESSAO", []) + rows.get("PREV_CNIS", []),
            )
        )

    # Lógica 7
    if _has_doc(rows, "PREV_CAT") and _has_doc(rows, "PROVA_BOLETIM_OCORRENCIA"):
        for bo in rows.get("PROVA_BOLETIM_OCORRENCIA", []):
            raw = str(bo).lower()
            if "trajeto" in raw:
                # simplificação: alerta sempre que houver menção de trajeto; refinamento temporal entra depois
                alerts.append(
                    LegalAlert(
                        code="ALERTA_ACIDENTE_TRAJETO_POS_REFORMA",
                        title="Acidente in itinere pós-reforma",
                        severity="média",
                        message="Há estabilidade, mas não há responsabilidade civil do empregador.",
                        supporting_facts=rows.get("PREV_CAT", []) + [bo],
                    )
                )
                break

    return alerts