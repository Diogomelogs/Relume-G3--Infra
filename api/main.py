import os
import uuid
import requests
import hashlib
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Body, HTTPException
from fastapi.responses import JSONResponse
from azure.storage.blob import BlobClient, ContainerClient
import openai

# ==========================
# Configurações do ambiente
# ==========================
APP_NAME = "relume-api"

CONTAINER_URL = os.environ["AZURE_STORAGE_URL"].rstrip("/")
ACCOUNT_KEY = os.environ["AZURE_STORAGE_KEY"]

VISION_ENDPOINT = os.environ["VISION_ENDPOINT"].rstrip("/")
VISION_KEY = os.environ["VISION_API_KEY"]

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_ENDPOINT = os.environ["OPENAI_ENDPOINT"]
OPENAI_DEPLOYMENT = os.environ["OPENAI_DEPLOYMENT"]  # gpt-35-turbo, etc.

# ==========================
# FastAPI
# ==========================
app = FastAPI(title="Relume API", version="0.2.0")

# ==========================
# Azure OpenAI
# ==========================
openai.api_type = "azure"
openai.api_key = OPENAI_API_KEY
openai.api_base = OPENAI_ENDPOINT
openai.api_version = "2023-05-15"


# Normalização do Logical ID
def _normalize_logical_id(filename: str) -> str:
    name, _ = os.path.splitext(filename)
    logical = name.strip().lower()

    for ch in [" ", ":", ";", ",", ".", "/", "\\", "|", "@", "#", "$", "%", "&",
               "?", "!", "(", ")", "[", "]"]:
        logical = logical.replace(ch, "_")

    while "__" in logical:
        logical = logical.replace("__", "_")

    logical = logical.strip("_")

    if not logical:
        logical = str(uuid.uuid4())

    return logical


# ==========================
# Endpoints básicos
# ==========================
@app.get("/")
def root():
    return {"message": "Relume API online"}


@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME}


# ==========================
# UPLOAD + VERSIONAMENTO + VISION BINÁRIA
# ==========================
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    """
    Pipeline:
    1. Lê arquivo
    2. Gera hash SHA256
    3. Cria logical_id
    4. Gera versão vYYYYMMDDTHHMMSSZ
    5. Envia ao Blob
    6. Grava metadados
    7. Envia conteúdo binário à Vision API
    """

    # 1) Lê arquivo
    data = await file.read()

    # 2) Hash de integridade
    file_hash = hashlib.sha256(data).hexdigest()

    # 3) Logical ID
    logical_id = _normalize_logical_id(file.filename)

    # 4) Versionamento lógico com timestamp UTC
    version_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    # 5) Caminho no Blob
    blob_name = f"{logical_id}/v{version_str}/{file.filename}"

    blob = BlobClient.from_blob_url(
        f"{CONTAINER_URL}/{blob_name}",
        credential=ACCOUNT_KEY,
    )

    blob.upload_blob(data, overwrite=True)

    # URL resultante do Blob
    blob_url = f"{CONTAINER_URL}/{blob_name}"

    # 6) Metadados
    metadata = {
        "original_filename": file.filename,
        "logical_id": logical_id,
        "version": version_str,
        "hash_sha256": file_hash,
        "uploaded_at": datetime.utcnow().isoformat() + "Z",
    }

    try:
        blob.set_blob_metadata(metadata)
    except Exception:
        pass  # não quebrar fluxo

    # ==========================
    # 7) Vision API com ANÁLISE BINÁRIA
    # ==========================
    analyze_url = (
        f"{VISION_ENDPOINT}/vision/v3.2/analyze"
        "?visualFeatures=Description,Tags,Faces"
    )

    headers = {
        "Ocp-Apim-Subscription-Key": VISION_KEY,
        "Content-Type": "application/octet-stream",
    }

    vision = {}

    try:
        r = requests.post(analyze_url, headers=headers, data=data, timeout=25)

        if r.ok:
            vision = r.json()
        else:
            vision = {
                "error": r.text,
                "status": r.status_code,
            }
    except Exception as ex:
        vision = {"error": str(ex)}

    # ==========================
    # Resposta ao cliente
    # ==========================
    return JSONResponse(
        {
            "blob": blob_url,
            "logical_id": logical_id,
            "version": version_str,
            "hash_sha256": file_hash,
            "vision": vision,
        }
    )


# ==========================
# NARRATE — geração de narrativa pelas tags
# ==========================
@app.post("/narrate")
async def narrate(data: dict = Body(...)):
    try:
        tags_list = data.get("tags", [])
        if not isinstance(tags_list, list):
            raise HTTPException(
                status_code=400,
                detail="Campo 'tags' deve ser uma lista de strings."
            )

        tags = ", ".join(tags_list) if tags_list else "memórias pessoais"

        prompt = (
            "Crie uma narrativa curta, emocional e sensível, em português, "
            f"sobre uma lembrança que envolve: {tags}."
        )

        response = openai.ChatCompletion.create(
            engine=OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7,
        )

        text = response.choices[0].message["content"].strip()

        return {"narrative": text}

    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))
