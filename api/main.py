import os, uuid, requests
from datetime import datetime, timedelta
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from azure.storage.blob import BlobClient, generate_blob_sas, BlobSasPermissions

APP_NAME = "relume-api"

def _getenv(k: str) -> str:
    v = os.getenv(k)
    if not v:
        raise RuntimeError(f"Variável de ambiente ausente: {k}")
    return v

CONTAINER_URL = _getenv("AZURE_STORAGE_URL").rstrip("/")     # ex: https://acc.blob.core.windows.net/uploads
ACCOUNT_KEY   = _getenv("AZURE_STORAGE_KEY")
VISION_EP     = _getenv("VISION_ENDPOINT").rstrip("/")       # ex: https://centralus.api.cognitive.microsoft.com
VISION_KEY    = _getenv("VISION_API_KEY")

app = FastAPI(title="Relume API", version="0.1.0")

@app.get("/")
def root():
    return {"message": "Relume API online"}

@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME}

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    try:
        # 1) grava no Blob
        blob_name = f"{uuid.uuid4()}_{file.filename}"
        blob = BlobClient.from_blob_url(f"{CONTAINER_URL}/{blob_name}", credential=ACCOUNT_KEY)
        data = await file.read()
        blob.upload_blob(data, overwrite=True)
        blob_url = f"{CONTAINER_URL}/{blob_name}"

        # 2) gera SAS de leitura por 10 min (container privado)
        sas = generate_blob_sas(
            account_name=blob.account_name,
            container_name=blob.container_name,
            blob_name=blob.blob_name,
            account_key=ACCOUNT_KEY,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(minutes=10)
        )
        sas_url = f"{blob.url}?{sas}"

        # 3) chama Vision (descrição + tags + faces)
        analyze_url = f"{VISION_EP}/vision/v3.2/analyze?visualFeatures=Description,Tags,Faces"
        headers = {"Ocp-Apim-Subscription-Key": VISION_KEY, "Content-Type": "application/json"}
        r = requests.post(analyze_url, headers=headers, json={"url": sas_url}, timeout=25)

        vision = r.json() if r.status_code < 300 else {"error": r.text, "status": r.status_code}

        return JSONResponse({"blob": blob_url, "vision": vision})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
