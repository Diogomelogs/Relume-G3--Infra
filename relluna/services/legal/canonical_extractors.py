from __future__ import annotations

import re
from typing import List, Dict, Any
from relluna.domain.legal_fields import CanonicalExtraction, CanonicalField, EvidenceAnchor
from relluna.domain.legal_taxonomy import DocType


RE_DATE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
RE_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b")
RE_RG = re.compile(r"\bRG[:\s\-]*([0-9A-Z\.\-]{5,20})\b", re.IGNORECASE)
RE_CEP = re.compile(r"\b\d{5}-\d{3}\b")
RE_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
RE_CRM = re.compile(r"\bCRM(?:\s*[-:/]?\s*[A-Z]{0,2})?\s*[-:]?\s*(\d{4,8})\b", re.IGNORECASE)
RE_NB = re.compile(r"\bNB[:\s\-]*([0-9\.\-]{8,20})\b", re.IGNORECASE)
RE_BEN_SPECIES = re.compile(r"\b(B31|B91|B92|B87|LOAS)\b", re.IGNORECASE)
RE_DIB = re.compile(r"\bDIB[:\s\-]*([0-9]{2}/[0-9]{2}/[0-9]{4})\b", re.IGNORECASE)
RE_DCB = re.compile(r"\bDCB[:\s\-]*([0-9]{2}/[0-9]{2}/[0-9]{4})\b", re.IGNORECASE)
RE_CID = re.compile(r"\b([A-TV-Z][0-9]{2}(?:\.[0-9A-Z]{1,2})?)\b")
RE_DAYS_OFF = re.compile(r"\b(\d{1,3})\s+dias?\s+de\s+afastamento\b", re.IGNORECASE)
RE_CA = re.compile(r"\bCA[:\s\-]*([0-9]{3,12})\b", re.IGNORECASE)

RE_FULLNAME = re.compile(
    r"(?:nome(?:\s+completo)?|nome\s+paciente)[:;\s]+([A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][A-ZÁÀÃÂÉÊÍÓÔÕÚÇ\s]{5,}?)(?=\s+Nascimento|\s+Sexo|\n|$)",
    re.IGNORECASE,
)
RE_ADDRESS = re.compile(r"(Avenida|Rua|Travessa|Alameda|Rodovia)\s+[A-Za-zÀ-ÿ0-9\s,\-]+", re.IGNORECASE)
RE_ADMISSION = re.compile(r"\bdata\s+de\s+admiss[aã]o[:\s\-]*([0-9]{2}/[0-9]{2}/[0-9]{4})", re.IGNORECASE)
RE_DISMISSAL = re.compile(r"\bdata\s+de\s+(?:demiss[aã]o|afastamento)[:\s\-]*([0-9]{2}/[0-9]{2}/[0-9]{4})", re.IGNORECASE)
RE_REMUN = re.compile(r"\b(?:ultima\s+remunera[cç][aã]o|remunera[cç][aã]o)[:\s\-]*R?\$?\s*([0-9\.\,]+)", re.IGNORECASE)
RE_ROLE = re.compile(r"\b(?:cargo|fun[cç][aã]o)[:\s\-]*([A-Za-zÀ-ÿ\s]{3,60})", re.IGNORECASE)
RE_EMPLOYER = re.compile(r"\b(?:raz[aã]o\s+social|empregador)[:\s\-]*([A-Za-zÀ-ÿ0-9\s\.\-\/]{4,120})", re.IGNORECASE)
RE_RESULT_ASO = re.compile(r"\b(apto|inapto)\b", re.IGNORECASE)
RE_DATA_ASO = re.compile(r"\b(?:data\s+aso|data\s+do\s+aso|em)\s*[:\-]?\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", re.IGNORECASE)


def _first(pattern: re.Pattern, text: str):
    m = pattern.search(text or "")
    return m.group(1).strip() if m else None


def _all(pattern: re.Pattern, text: str) -> List[str]:
    values = pattern.findall(text or "")
    out = []
    seen = set()
    for v in values:
        val = v if isinstance(v, str) else v[0]
        key = val.lower()
        if key not in seen:
            seen.add(key)
            out.append(val.strip())
    return out


def _field(name: str, value: Any, doc_type: str, confidence: float = 0.85) -> CanonicalField:
    return CanonicalField(
        name=name,
        value=value,
        normalized_value=value,
        confidence=confidence if value not in (None, "", []) else 0.0,
        source_doc_type=doc_type,
        anchor=EvidenceAnchor(page=1, bbox=None, snippet=None),
    )


def extract_canonical_fields(document_id: str, doc_type: str, text: str) -> CanonicalExtraction:
    fields: List[CanonicalField] = []

    if doc_type in {
        DocType.DOC_PESSOAL_RG.value,
        DocType.DOC_PESSOAL_CPF.value,
        DocType.DOC_PESSOAL_CNH.value,
        DocType.DOC_COMPROVANTE_RESIDENCIA.value,
    }:
        fields.extend([
            _field("Nome_Completo", _first(RE_FULLNAME, text), doc_type),
            _field("Data_Nascimento", _first(RE_DATE, text), doc_type),
            _field("Numero_RG", _first(RE_RG, text), doc_type),
            _field("Numero_CPF", _first(RE_CPF, text), doc_type),
            _field("CEP", _first(RE_CEP, text), doc_type),
            _field("Endereco_Completo", _first(RE_ADDRESS, text), doc_type),
        ])

    elif doc_type in {
        DocType.TRAB_CTPS.value,
        DocType.TRAB_TRCT.value,
        DocType.TRAB_HOLERITE.value,
        DocType.TRAB_FICHA_REGISTRO.value,
    }:
        fields.extend([
            _field("CNPJ_Empregador", _first(RE_CNPJ, text), doc_type),
            _field("Razao_Social", _first(RE_EMPLOYER, text), doc_type),
            _field("Cargo", _first(RE_ROLE, text), doc_type),
            _field("Data_Admissao", _first(RE_ADMISSION, text), doc_type),
            _field("Data_Demissao", _first(RE_DISMISSAL, text), doc_type),
            _field("Ultima_Remuneracao", _first(RE_REMUN, text), doc_type),
        ])

    elif doc_type in {
        DocType.PREV_CAT.value,
        DocType.PREV_CNIS.value,
        DocType.PREV_CARTA_CONCESSAO.value,
        DocType.PREV_CARTA_INDEFERIMENTO.value,
        DocType.PREV_LAUDO_SABI.value,
        DocType.PREV_PROCESSO_ADM_INTEGRAL.value,
    }:
        indeferimento = None
        if doc_type == DocType.PREV_CARTA_INDEFERIMENTO.value:
            indeferimento = "motivo não estruturado"

        fields.extend([
            _field("Numero_Beneficio", _first(RE_NB, text), doc_type),
            _field("Especie_Beneficio", _first(RE_BEN_SPECIES, text), doc_type),
            _field("DIB", _first(RE_DIB, text), doc_type),
            _field("DCB", _first(RE_DCB, text), doc_type),
            _field("CID_INSS", (_all(RE_CID, text) or [None])[0], doc_type),
            _field("Motivo_Indeferimento", indeferimento, doc_type, confidence=0.40 if indeferimento else 0.0),
        ])

    elif doc_type in {
        DocType.MED_ATESTADO.value,
        DocType.MED_RECEITUARIO.value,
        DocType.MED_PRONTUARIO_CLINICO.value,
        DocType.MED_EXAME_IMAGEM.value,
        DocType.MED_AUDIOMETRIA.value,
        DocType.MED_LAUDO_ASSISTENTE_TECNICO.value,
    }:
        conclusion = None
        lower = text.lower()
        for term in ["degenerativo", "extrusão discal", "extrusao discal", "pairo"]:
            if term in lower:
                conclusion = term
                break

        fields.extend([
            _field("Data_Documento", (_all(RE_DATE, text) or [None])[-1] if _all(RE_DATE, text) else None, doc_type),
            _field("CRM_Medico", (_all(RE_CRM, text) or [None])[0], doc_type),
            _field("CID_Atestado", (_all(RE_CID, text) or [None])[0], doc_type),
            _field("Dias_Afastamento", _first(RE_DAYS_OFF, text), doc_type),
            _field("Conclusao_Exame", conclusion, doc_type, confidence=0.75 if conclusion else 0.0),
        ])

    elif doc_type in {
        DocType.SST_ASO_ADMISSIONAL.value,
        DocType.SST_ASO_DEMISSIONAL.value,
        DocType.SST_ASO_RETORNO.value,
        DocType.SST_ASO_PERIODICO.value,
        DocType.SST_PCMSO.value,
        DocType.SST_PGR_PPRA.value,
        DocType.SST_AET.value,
        DocType.SST_LTCAT.value,
        DocType.SST_PPP.value,
        DocType.SST_FICHA_EPI.value,
    }:
        lower = text.lower()
        agente = None
        for term in ["ruído", "ruido", "sílica", "silica", "postura", "agrotóxicos", "agrotoxicos"]:
            if term in lower:
                agente = term
                break

        epi_dates = _all(RE_DATE, text)
        data_entrega = epi_dates[0] if epi_dates else None

        fields.extend([
            _field("Data_ASO", _first(RE_DATA_ASO, text), doc_type),
            _field("Resultado_ASO", _first(RE_RESULT_ASO, text), doc_type),
            _field("Agente_Nocivo", agente, doc_type, confidence=0.70 if agente else 0.0),
            _field("Numero_CA_EPI", _first(RE_CA, text), doc_type),
            _field("Data_Entrega_EPI", data_entrega, doc_type, confidence=0.65 if data_entrega else 0.0),
        ])

    return CanonicalExtraction(
        document_id=document_id,
        doc_type=doc_type,
        confidence=max((f.confidence for f in fields), default=0.0),
        fields=fields,
    )