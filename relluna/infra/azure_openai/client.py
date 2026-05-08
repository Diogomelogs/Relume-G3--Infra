from __future__ import annotations

import os
import json
import requests
from typing import Any

from relluna.infra.secrets import get_secret

def chat_json(*, system: str, user_json: dict[str, Any], json_schema: dict[str, Any]) -> dict[str, Any]:
    endpoint = get_secret("AZURE_OPENAI_ENDPOINT")
    key = get_secret("AZURE_OPENAI_API_KEY")
    deployment = get_secret("AZURE_OPENAI_CHAT_DEPLOYMENT")
    api_version = get_secret("AZURE_OPENAI_API_VERSION", default="2024-02-15-preview")

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
    endpoint = get_secret("AZURE_OPENAI_ENDPOINT")
    key = get_secret("AZURE_OPENAI_API_KEY")
    deployment = get_secret("AZURE_OPENAI_EMBED_DEPLOYMENT")
    api_version = get_secret("AZURE_OPENAI_API_VERSION", default="2024-02-15-preview")

    url = f"{endpoint}/openai/deployments/{deployment}/embeddings?api-version={api_version}"
    headers = {"api-key": key, "content-type": "application/json"}
    payload = {"input": text}

    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data["data"][0]["embedding"]