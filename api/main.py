import os
import uuid
import requests
import hashlib
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Body, HTTPException
from fastapi.responses import JSONResponse
from azure.storage.blob import BlobClient, ContainerClient
import openai

# ===== Configurações do ambiente =====
APP_NAME = "relume-api"
CONTAINER_URL = os.environ["AZURE_STORAGE_URL"].rstrip("/")  # URL do container
ACCOUNT_KEY = os.environ["AZURE_STORAGE_KEY"]
VISION_ENDPOINT = os.environ["VISION_ENDPOINT"].rstrip("/")
VISION_KEY = os.environ["VISION_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_ENDPOINT = os.environ["OPENAI_ENDPOINT"]
OPENAI_DEPLOYMENT = os.environ["OPENAI_DEPLOYMENT"]  # ex.: gpt-35-turbo

# ===== FastAPI =====
app = FastAPI(title="Relume API", version="0.1.3")

# ===== OpenAI (Azure) =====
openai.api_type = "azure"
openai.api_key = OPENAI_API_KEY
openai.api_base = OPENAI_ENDPOINT
openai.api_version = "2023-05-15"


def _get_container_client() -> ContainerClient:
    """
    Retorna um ContainerClient baseado na URL do container e na chave da conta.
    Usado para listar blobs e calcular a próxima versão lógica.
    """
    return ContainerClient.from_container_url(CONTAINER_URL, credential=ACCOUNT_KEY)


def _normalize_logical_id(filename: str) -> str:
    """
    Cria um identificador lógico a partir do nome do arquivo.
    Ex.: 'Foto Aniversário.jpg' -> 'foto_aniversario'
    """
    name, _ = os.path.splitext(filename)
    logical = name.strip().lower()
    for ch in [" ", ":", ";", ",", ".", "/", "\\", "|", "@", "#", "$", "%", "&", "?", "!", "(", ")", "[", "]"]:
        logical = logical.replace(ch, "_")
    while "__" in logical:
        logical = logical.replace("__", "_")
    logical = logical.strip("_")
    if not logical:
        logical = str(uuid.uuid4())
    return logical


@app.get("/")
def root():
    return {"message": "Relume API online"}


@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    """
    Upload com versionamento lógico:
    - logical_id derivado do nome do arquivo
    - versão = quantidade de blobs existentes com prefixo logical_id/ + 1
    - nome no Blob: logical_id/v{versao}/{arquivo_original}
    - metadados: original_filename, logical_id, version, hash_sha256, uploaded_at
    """
    # 0) Leitura do arquivo em memória
    data = await file.read()

    # 1) Hash SHA-256 para integridade
    file_hash = hashlib.sha256(data).hexdigest()

    # 2) Calcula logical_id a partir do nome do arquivo
    logical_id = _normalize_logical_id(file.filename)

    # 3) Descobre a próxima versão lógica no container
    container_client = _get_container_client()
    prefix = f"{logical_id}/"
    existing = list(container_client.list_blobs(name_starts_with=prefix))
    next_version = len(existing) + 1

    # 4) Monta o nome do blob com versionamento lógico
    blob_name = f"{logical_id}/v{next_version}/{file.filename}"

    # 5) Faz o upload no Blob Storage
    blob = BlobClient.from_blob_url(
        f"{CONTAINER_URL}/{blob_name}", credential=ACCOUNT_KEY
    )
    blob.upload_blob(data, overwrite=True)
    blob_url = f"{CONTAINER_URL}/{blob_name}"

    # 6) Grava metadados no blob
    metadata = {
        "original_filename": file.filename,
        "logical_id": logical_id,
        "version": str(next_version),
        "hash_sha256": file_hash,
        "uploaded_at": datetime.utcnow().isoformat() + "Z",
    }
    try:
        blob.set_blob_metadata(metadata)
    except Exception:
        # falha em metadados não deve impedir o fluxo principal
        pass

    # 7) Vision: descrição/tags/faces
    analyze_url = (
        f"{VISION_ENDPOINT}/vision/v3.2/analyze"
        "?visualFeatures=Description,Tags,Faces"
    )
    headers = {
        "Ocp-Apim-Subscription-Key": VISION_KEY,
        "Content-Type": "application/json",
    }
    payload = {"url": blob_url}

    vision = {"note": "se o contêiner for privado, use SAS URL para análise"}
    try:
        r = requests.post(analyze_url, headers=headers, json=payload, timeout=20)
        if r.ok:
            vision = r.json()
        else:
            vision = {"error": r.text, "status": r.status_code}
    except Exception as ex:
        vision = {"error": str(ex)}

    return JSONResponse(
        {
            "blob": blob_url,
            "logical_id": logical_id,
            "version": next_version,
            "hash_sha256": file_hash,
            "vision": vision,
        }
    )


@app.post("/narrate")
async def narrate(data: dict = Body(...)):
    try:
        # validação básica do payload
        tags_list = data.get("tags", [])
        if not isinstance(tags_list, list):
            raise HTTPException(
                status_code=400,
                detail="Campo 'tags' deve ser uma lista de strings.",
            )

        tags = ", ".join(tags_list) if tags_list else "memórias pessoais"
        prompt = (
            "Crie uma narrativa curta e emocional em português sobre uma lembrança "
            f"que envolve: {tags}."
        )

        # chamada ao Azure OpenAI
        response = openai.ChatCompletion.create(
            engine=OPENAI_DEPLOYMENT,  # usa o deployment configurado (gpt-35-turbo)
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.7,
        )

        text = response.choices[0].message["content"].strip()
        return {"narrative": text}

    except openai.error.OpenAIError as oe:
        # erros vindos do Azure OpenAI (deployment, quota, etc.)
        raise HTTPException(status_code=502, detail=f"OpenAI error: {str(oe)}")
    except Exception as e:
        # qualquer outro erro interno
        raise HTTPException(status_code=500, detail=str(e))
