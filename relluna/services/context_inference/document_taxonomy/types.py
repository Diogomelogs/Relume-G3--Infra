from enum import Enum


class DocumentType(str, Enum):
    """
    Contrato público de tipo semântico do documento.

    v1 congelado.
    """

    desconhecido = "desconhecido"
    recibo = "recibo"
    nota_fiscal = "nota_fiscal"
    identidade = "identidade"
    contrato = "contrato"
    fatura = "fatura"
    extrato = "extrato"
    midia = "midia"
