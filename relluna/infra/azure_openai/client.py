from __future__ import annotations

import os
import json
import requests
from typing import Any

def _get_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v

def chat_json(*, system: str, user_json: dict[str, Any], json_schema: dict[str, Any]) -> dict[str, Any]:
    endpoint = _get_env("AZURE_OPENAI_ENDPOINT")
    key = _get_env("AZURE_OPENAI_API_KEY")
    deployment = _get_env("AZURE_OPENAI_CHAT_DEPLOYMENT")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    headers = {"api-key": key, "content-type": "application/json"}

    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_json, ensure_ascii=False)},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    out = json.loads(content)

    # Validação leve: garantir chaves obrigatórias (schema estrito pode ser validado depois)
    for k in json_schema.get("required", []):
        if k not in out:
            raise ValueError(f"LLM output missing required key: {k}")
    return out

def embed_text(text: str) -> list[float]:
    endpoint = _get_env("AZURE_OPENAI_ENDPOINT")
    key = _get_env("AZURE_OPENAI_API_KEY")
    deployment = _get_env("AZURE_OPENAI_EMBED_DEPLOYMENT")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    url = f"{endpoint}/openai/deployments/{deployment}/embeddings?api-version={api_version}"
    headers = {"api-key": key, "content-type": "application/json"}
    payload = {"input": text}

    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data["data"][0]["embedding"]