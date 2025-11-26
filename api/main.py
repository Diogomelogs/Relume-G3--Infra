import os
import uuid
import requests
import hashlib
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Body, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware  # <--- ADICIONADO
from azure.storage.blob import BlobClient
import openai
from pymongo import MongoClient

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
OPENAI_DEPLOYMENT = os.environ["OPENAI_DEPLOYMENT"]  # ex.: gpt-35-turbo

MONGO_URI = os.environ.get("MONGO_URI")  # string de conexão do MongoDB Atlas

# ==========================
# FastAPI
# ==========================
app = FastAPI(title="Relume API", version="0.3.0")

# ==========================
# CORS (liberar chamadas do front)
# ==========================
origins = [
    "http://localhost:3000",
    "https://relume-api-ajeyfjcgbwhubdec.centralus-01.azurewebsites.net",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================
# Azure OpenAI
# ==========================
openai.api_type = "azure"
openai.api_key = OPENAI_API_KEY
openai.api_base = OPENAI_ENDPOINT
openai.api_version = "2023-05-15"

# ==========================
# MongoDB (timeline)
# ==========================
mongo_client = None
timeline_coll = None

if MONGO_URI:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["relume"]
    timeline_coll = db["timeline_items"]


# ==========================
# Funções auxiliares
# ==========================
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
    return {
        "status": "ok",
        "app": APP_NAME,
        "mongo_connected": bool(timeline_coll is not None),
    }


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
    5. Envia ao Blob (container privado)
    6. Grava metadados
    7. Envia conteúdo binário à Vision API
    8. Retorna dados para possível uso em /process
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
        # falha de metadado não interrompe o fluxo principal
        pass

    # 7) Vision API com BINÁRIO
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
            vision = {"error": r.text, "status": r.status_code}
    except Exception as ex:
        vision = {"error": str(ex)}

    # 8) Resposta
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
# /process — grava na timeline (MongoDB)
# ==========================
@app.post("/process")
async def process_media(payload: dict = Body(...)):
    """
    Espera um payload no formato:

    {
      "user_id": "abc123",
      "blob": "https://.../uploads/...",
      "hash_sha256": "...",
      "logical_id": "img_5285",
      "version": "20251117T201038Z",
      "vision": {
        "tags": [...],
        "description": {...},
        "faces": [...]
      }
    }

    Grava um documento em timeline_items.
    """

    if timeline_coll is None:
        raise HTTPException(
            status_code=500,
            detail="MongoDB não configurado. Defina MONGO_URI no App Service."
        )

    user_id = payload.get("user_id")
    blob_url = payload.get("blob")
    file_hash = payload.get("hash_sha256")
    logical_id = payload.get("logical_id")
    version = payload.get("version")
    vision = payload.get("vision", {}) or {}

    if not user_id or not blob_url:
        raise HTTPException(
            status_code=400,
            detail="Campos 'user_id' e 'blob' são obrigatórios."
        )

    tags = vision.get("tags", [])
    description = vision.get("description", {})
    faces = vision.get("faces", [])

    # extrai caption principal, se existir
    main_caption = None
    try:
        captions = description.get("captions", [])
        if captions:
            main_caption = captions[0].get("text")
    except Exception:
        main_caption = None

    doc = {
        "user_id": user_id,
        "blob_url": blob_url,
        "hash_sha256": file_hash,
        "logical_id": logical_id,
        "version": version,
        "vision_tags": tags,
        "vision_description": description,
        "vision_faces": faces,
        "main_caption": main_caption,
        "created_at": datetime.utcnow(),
    }

    result = timeline_coll.insert_one(doc)

    return {
        "saved": True,
        "id": str(result.inserted_id),
        "user_id": user_id,
        "blob_url": blob_url,
    }


# ==========================
# /timeline — retorna timeline por usuário
# ==========================
@app.get("/timeline")
def get_timeline(user_id: str):
    """
    Retorna todos os itens da timeline de um usuário, ordenados por created_at desc.

    GET /timeline?user_id=abc123
    """

    if timeline_coll is None:
        raise HTTPException(
            status_code=500,
            detail="MongoDB não configurado. Defina MONGO_URI no App Service."
        )

    items = list(
        timeline_coll.find({"user_id": user_id}).sort("created_at", -1)
    )

    for item in items:
        item["_id"] = str(item["_id"])
        # converte datetime para string ISO
        if isinstance(item.get("created_at"), datetime):
            item["created_at"] = item["created_at"].isoformat() + "Z"

    return items


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
