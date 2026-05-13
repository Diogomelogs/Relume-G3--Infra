from __future__ import annotations

from typing import List, Dict, Any


HEADER_RULES = {
    "MED_RECEITUARIO": ["receituario", "orientacao ao paciente", "retencao da farmacia"],
    "PREV_CAT": ["comunicacao de acidente de trabalho", "cat"],
    "PREV_CARTA_CONCESSAO": ["carta de concessão", "carta de concessao", "nb", "dib"],
    "PREV_CARTA_INDEFERIMENTO": ["indeferimento", "pedido negado", "benefício indeferido", "beneficio indeferido"],
    "MED_PRONTUARIO_CLINICO": ["prontuário", "prontuario", "evolução", "evolucao", "anamnese", "atendimento"],
    "MED_EXAME_IMAGEM": ["ressonância", "ressonancia", "tomografia", "radiografia", "impressão diagnóstica", "impressao diagnostica"],
    "MED_AUDIOMETRIA": ["audiometria", "limiar auditivo", "perda auditiva"],
    "SST_ASO_ADMISSIONAL": ["aso", "admissional"],
    "SST_ASO_DEMISSIONAL": ["aso", "demissional"],
    "SST_ASO_RETORNO": ["aso", "retorno ao trabalho"],
    "SST_ASO_PERIODICO": ["aso", "periódico", "periodico"],
    "SST_PPP": ["perfil profissiográfico previdenciário", "perfil profissiografico previdenciario", "ppp"],
    "SST_FICHA_EPI": ["ficha de epi", "equipamento de proteção individual", "equipamento de protecao individual", "ca "],
    "TRAB_TRCT": ["termo de rescisão", "termo de rescisao", "verbas rescisórias", "verbas rescisorias"],
    "TRAB_HOLERITE": ["recibo de pagamento", "liquido", "salário base", "salario base"],
    "TRAB_CTPS": ["carteira de trabalho", "contrato de trabalho"],
    "PROVA_BOLETIM_OCORRENCIA": ["boletim de ocorrência", "boletim de ocorrencia", "delegacia"],
    "PROVA_ATA_NOTARIAL": ["ata notarial", "tabelião", "tabeliao"],
}


def detect_page_doc_type(page_text: str) -> str:
    t = (page_text or "").lower()

    best_type = "UNKNOWN"
    best_score = 0

    for doc_type, keys in HEADER_RULES.items():
        score = sum(1 for k in keys if k in t)
        if score > best_score:
            best_score = score
            best_type = doc_type

    if best_score == 0:
        if "hospital" in t or "crm" in t or "paciente" in t:
            return "MED_PRONTUARIO_CLINICO"
        return "UNKNOWN"

    return best_type


def split_into_subdocuments(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Entrada:
      pages = [{"page": 1, "text": "...", ...}, ...]

    Saída:
      [
        {
          "subdoc_id": "...",
          "doc_type": "...",
          "pages": [1,2],
          "page_map": [{"page":1,"text":"..."},{"page":2,"text":"..."}],
          "text": "concat do subdoc"
        }
      ]
    """
    subdocs: List[Dict[str, Any]] = []
    current: Dict[str, Any] | None = None

    for page in pages:
        page_no = page["page"]
        page_text = page["text"]
        page_type = detect_page_doc_type(page_text)

        if current is None:
            current = {
                "subdoc_id": f"subdoc_{len(subdocs)+1:03d}",
                "doc_type": page_type,
                "pages": [page_no],
                "page_map": [{"page": page_no, "text": page_text}],
            }
            continue

        if page_type != current["doc_type"] and page_type != "UNKNOWN":
            current["text"] = "\n\n".join(item["text"] for item in current["page_map"])
            subdocs.append(current)
            current = {
                "subdoc_id": f"subdoc_{len(subdocs)+1:03d}",
                "doc_type": page_type,
                "pages": [page_no],
                "page_map": [{"page": page_no, "text": page_text}],
            }
        else:
            current["pages"].append(page_no)
            current["page_map"].append({"page": page_no, "text": page_text})

    if current is not None:
        current["text"] = "\n\n".join(item["text"] for item in current["page_map"])
        subdocs.append(current)

    return subdocs