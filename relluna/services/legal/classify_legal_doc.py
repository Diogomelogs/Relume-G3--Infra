from __future__ import annotations

from typing import Dict, Any
from relluna.domain.legal_taxonomy import DocType


def classify_legal_doc(page_text: str) -> Dict[str, Any]:
    t = (page_text or "").lower()

    rules = [
        (DocType.DOC_PESSOAL_RG, ["registro geral", "rg", "secretaria de seguranca"]),
        (DocType.DOC_PESSOAL_CPF, ["cadastro de pessoas fisicas", "cpf", "receita federal"]),
        (DocType.DOC_PESSOAL_CNH, ["carteira nacional de habilitacao", "permissao para dirigir", "categoria"]),
        (DocType.DOC_COMPROVANTE_RESIDENCIA, ["cep", "logradouro", "codigo do cliente", "vencimento"]),
        (DocType.DOC_PROCURACAO, ["outorgante", "outorgado", "procuração", "poderes"]),
        (DocType.DOC_CONTRATO_HONORARIOS, ["contrato de honorarios", "honorários advocatícios", "clausula"]),
        (DocType.DOC_DECLARACAO_HIPOSSUFICIENCIA, ["declaro", "hipossuficiência", "não possuo condições"]),

        (DocType.TRAB_CTPS, ["carteira de trabalho", "contrato de trabalho", "admissão", "remuneração"]),
        (DocType.TRAB_TRCT, ["termo de rescisão", "rescisao", "data de afastamento", "verbas rescisórias"]),
        (DocType.TRAB_HOLERITE, ["recibo de pagamento", "salário base", "líquido", "descontos"]),
        (DocType.TRAB_FICHA_REGISTRO, ["ficha de registro", "empregado", "cargo", "admissão"]),

        (DocType.PREV_CAT, ["comunicacao de acidente de trabalho", "cat", "emitente"]),
        (DocType.PREV_CNIS, ["cnis", "cadastro nacional de informações sociais", "competência"]),
        (DocType.PREV_CARTA_CONCESSAO, ["carta de concessão", "nb", "dib", "rmi"]),
        (DocType.PREV_CARTA_INDEFERIMENTO, ["indeferimento", "motivo", "pedido negado"]),
        (DocType.PREV_LAUDO_SABI, ["sabi", "perícia médica federal", "conclusão pericial"]),
        (DocType.PREV_PROCESSO_ADM_INTEGRAL, ["processo administrativo", "inss", "recurso", "decisão"]),

        (DocType.MED_ATESTADO, ["atesto para os devidos fins", "dias de afastamento", "cid"]),
        (DocType.MED_RECEITUARIO, ["receituario", "orientacao ao paciente", "retencao da farmacia"]),
        (DocType.MED_PRONTUARIO_CLINICO, ["prontuário", "evolução", "anamnese", "atendimento"]),
        (DocType.MED_EXAME_IMAGEM, ["ressonância", "tomografia", "radiografia", "laudo", "impressão diagnóstica"]),
        (DocType.MED_AUDIOMETRIA, ["audiometria", "limiar auditivo", "perda auditiva"]),
        (DocType.MED_LAUDO_ASSISTENTE_TECNICO, ["assistente técnico", "parecer técnico", "quesitos"]),

        (DocType.SST_ASO_ADMISSIONAL, ["aso", "admissional", "apto", "inapto"]),
        (DocType.SST_ASO_DEMISSIONAL, ["aso", "demissional", "apto", "inapto"]),
        (DocType.SST_ASO_RETORNO, ["aso", "retorno ao trabalho", "apto", "inapto"]),
        (DocType.SST_ASO_PERIODICO, ["aso", "periódico", "apto", "inapto"]),
        (DocType.SST_PCMSO, ["pcmso", "programa de controle médico de saúde ocupacional"]),
        (DocType.SST_PGR_PPRA, ["pgr", "ppra", "programa de prevenção de riscos ambientais"]),
        (DocType.SST_AET, ["análise ergonômica", "aet", "ergonomia"]),
        (DocType.SST_LTCAT, ["ltcat", "laudo técnico das condições ambientais do trabalho"]),
        (DocType.SST_PPP, ["perfil profissiográfico previdenciário", "ppp"]),
        (DocType.SST_FICHA_EPI, ["ficha de epi", "ca", "equipamento de proteção individual"]),

        (DocType.PROVA_BOLETIM_OCORRENCIA, ["boletim de ocorrência", "delegacia", "histórico da ocorrência"]),
        (DocType.PROVA_PRINT_MENSAGEM, ["whatsapp", "mensagem", "conversa"]),
        (DocType.PROVA_FOTO_AMBIENTE, ["imagem", "fotografia", "ambiente"]),
        (DocType.PROVA_ATA_NOTARIAL, ["ata notarial", "tabelião", "fé pública"]),
    ]

    best = (DocType.UNKNOWN, 0)
    for dtype, keywords in rules:
        score = sum(1 for k in keywords if k in t)
        if score > best[1]:
            best = (dtype, score)

    if best[1] == 0:
        return {"doc_type": DocType.UNKNOWN.value, "confidence": 0.10}

    return {
        "doc_type": best[0].value,
        "confidence": min(0.50 + 0.10 * best[1], 0.97),
    }