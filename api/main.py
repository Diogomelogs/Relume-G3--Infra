import os, uuid, requests
from fastapi import FastAPI, UploadFile, File, Body, HTTPException
from fastapi.responses import JSONResponse
from azure.storage.blob import BlobClient
import openai

# ===== Configurações do ambiente =====
APP_NAME = "relume-api"
CONTAINER_URL = os.environ["AZURE_STORAGE_URL"].rstrip("/")
ACCOUNT_KEY = os.environ["AZURE_STORAGE_KEY"]
VISION_ENDPOINT = os.environ["VISION_ENDPOINT"].rstrip("/")
VISION_KEY = os.environ["VISION_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_ENDPOINT = os.environ["OPENAI_ENDPOINT"]
OPENAI_DEPLOYMENT = os.environ["OPENAI_DEPLOYMENT"]  # nome do deployment (ex.: gpt-35-turbo)

# ===== FastAPI =====
app = FastAPI(title="Relume API", version="0.1.2")

# ===== OpenAI (Azure) =====
openai.api_type = "azure"
openai.api_key = OPENAI_API_KEY
openai.api_base = OPENAI_ENDPOINT
openai.api_version = "2023-05-15"

@app.get("/")
def root():
    return {"message": "Relume API online"}

@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME}

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    # 1) Grava no Blob
    blob_name = f"{uuid.uuid4()}_{file.filename}"
    blob = BlobClient.from_blob_url(f"{CONTAINER_URL}/{blob_name}", credential=ACCOUNT_KEY)
    data = await file.read()
    blob.upload_blob(data, overwrite=True)
    blob_url = f"{CONTAINER_URL}/{blob_name}"

    # 2) Vision: descrição/tags/faces
    analyze_url = f"{VISION_ENDPOINT}/vision/v3.2/analyze?visualFeatures=Description,Tags,Faces"
    headers = {"Ocp-Apim-Subscription-Key": VISION_KEY, "Content-Type": "application/json"}
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

    return JSONResponse({"blob": blob_url, "vision": vision})

@app.post("/narrate")
async def narrate(data: dict = Body(...)):
    try:
        tags_list = data.get("tags", [])
        if not isinstance(tags_list, list):
            raise HTTPException(status_code=400, detail="Campo 'tags' deve ser uma lista de strings.")
        tags = ", ".join(tags_list) if tags_list else "memórias pessoais"

        prompt = f"Crie uma narrativa curta e emocional em português sobre uma lembrança que envolve: {tags}."

        response = openai.ChatCompletion.create(
    engine="gpt-35-turbo"
    messages=[{"role": "user", "content": prompt}],
    max_tokens=120
)
        text = resp.choices[0].message["content"].strip()
        return {"narrative": text}

    except openai.error.OpenAIError as oe:
        raise HTTPException(status_code=502, detail=f"OpenAI error: {str(oe)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
