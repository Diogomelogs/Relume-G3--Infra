# relluna/services/structured_block.py

import re
from datetime import datetime
from typing import Dict, List, Optional


def is_contrato(texto: str) -> bool:
    texto_up = texto.upper()
    return (
        "CONTRATO" in texto_up
        and "PARTES" in texto_up
    )


def extract_partes(texto: str) -> List[Dict]:
    partes = []

    # CONTRATANTE
    match_contratante = re.search(
        r"Empresa:\s*(.+?),\s*.*?CNPJ:\s*([\d./-]+)",
        texto,
        re.IGNORECASE | re.DOTALL
    )

    if match_contratante:
        partes.append({
            "papel": "contratante",
            "nome": match_contratante.group(1).strip(),
            "cnpj": match_contratante.group(2),
        })

    # CONTRATADO
    match_contratado = re.search(
        r"Influenciador.*?:\s*(.+?),.*?CPF:\s*([\d.-]+)",
        texto,
        re.IGNORECASE | re.DOTALL
    )

    if match_contratado:
        partes.append({
            "papel": "contratado",
            "nome": match_contratado.group(1).strip(),
            "cpf": match_contratado.group(2),
        })

    return partes


def extract_vigencia(texto: str) -> Dict:
    match = re.search(
        r"vig[êe]ncia.*?(\d{2}\s+de\s+\w+\s+de\s+\d{4}).*?(\d{2}\s+de\s+\w+\s+de\s+\d{4})",
        texto,
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        return {}

    return {
        "inicio_texto": match.group(1),
        "fim_texto": match.group(2)
    }


def extract_valores(texto: str) -> List[str]:
    valores = re.findall(r"R\$\s?[\d.,]+", texto)
    return list(set(valores))


def extract_prazos(texto: str) -> List[str]:
    prazos = []

    dias = re.findall(r"\d+\s*dias?", texto, re.IGNORECASE)
    horas = re.findall(r"\d+\s*horas?", texto, re.IGNORECASE)

    prazos.extend(dias)
    prazos.extend(horas)

    return list(set(prazos))


def build_structured_block(texto: str) -> Optional[Dict]:
    """
    Retorna estrutura mínima para contratos.
    Se não for contrato, retorna None.
    """

    if not is_contrato(texto):
        return None

    return {
        "tipo_estrutura": "contrato",
        "partes": extract_partes(texto),
        "vigencia": extract_vigencia(texto),
        "valores": extract_valores(texto),
        "prazos": extract_prazos(texto),
    }