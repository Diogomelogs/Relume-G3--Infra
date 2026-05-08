"""Carregamento de segredos com fallback dev/prod.

Em desenvolvimento (APP_ENV=development), lê de variáveis de ambiente
populadas pelo .env. Em produção (APP_ENV=production), tenta primeiro
variáveis de ambiente, depois Azure Key Vault.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional


@lru_cache(maxsize=None)
def get_secret(name: str, default: Optional[str] = None) -> str:
    """Resolve um segredo com fallback ordenado.

    Ordem:
    1. Variável de ambiente (preenchida em dev pelo .env)
    2. Azure Key Vault (em prod, se APP_ENV=production e AZURE_KEYVAULT_URL definido)
    3. Default fornecido (ou RuntimeError se obrigatório)

    Args:
        name: Nome da variável (ex: AZURE_OPENAI_API_KEY)
        default: Valor padrão se não encontrado em nenhuma fonte

    Returns:
        Valor do segredo

    Raises:
        RuntimeError: Se o segredo é obrigatório e não foi encontrado
    """
    value = os.environ.get(name)
    if value:
        return value

    if os.environ.get("APP_ENV") == "production":
        kv_value = _get_from_keyvault(name)
        if kv_value:
            return kv_value

    if default is not None:
        return default

    raise RuntimeError(
        f"Segredo obrigatório '{name}' não encontrado em variáveis de ambiente "
        f"nem no Azure Key Vault. Verifique a configuração de APP_ENV e "
        f"AZURE_KEYVAULT_URL."
    )


def _get_from_keyvault(name: str) -> Optional[str]:
    """Busca segredo no Azure Key Vault usando DefaultAzureCredential.

    Convenção: nomes em SCREAMING_CASE viram secret-name em kebab-case.
    Ex: AZURE_OPENAI_API_KEY -> azure-openai-api-key
    """
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError:
        return None

    vault_url = os.environ.get("AZURE_KEYVAULT_URL")
    if not vault_url:
        return None

    try:
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=vault_url, credential=credential)
        secret_name = name.lower().replace("_", "-")
        secret = client.get_secret(secret_name)
        return secret.value
    except Exception:
        return None
