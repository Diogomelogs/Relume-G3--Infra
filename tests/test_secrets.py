"""Testes para o módulo de carregamento de segredos."""
import os
import pytest
from unittest.mock import patch

from relluna.infra.secrets import get_secret


def setup_function():
    get_secret.cache_clear()


def test_get_secret_from_env():
    with patch.dict(os.environ, {"TEST_SECRET": "value123"}):
        assert get_secret("TEST_SECRET") == "value123"


def test_get_secret_with_default():
    with patch.dict(os.environ, {}, clear=True):
        assert get_secret("MISSING_SECRET", default="fallback") == "fallback"


def test_get_secret_raises_when_obrigatorio():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="Segredo obrigatório"):
            get_secret("MISSING_SECRET")


def test_get_secret_prefers_env_over_keyvault():
    with patch.dict(os.environ, {
        "TEST_SECRET": "from_env",
        "APP_ENV": "production",
        "AZURE_KEYVAULT_URL": "https://fake.vault.azure.net",
    }):
        assert get_secret("TEST_SECRET") == "from_env"
