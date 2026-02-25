from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from hashlib import sha256
from pathlib import Path
import shutil
import uuid
from datetime import datetime

from relluna.core.document_memory import DocumentMemory, MediaType, OriginType, ArtefatoBruto
from relluna.core.basic_pipeline import run_basic_pipeline
from relluna.services.context_inference.basic import infer_layer3
from relluna.services.correlation.layer4 import apply_layer4
from relluna.services.context_inference.basic import infer_layer3
from relluna.services.correlation.layer4 import apply_layer4
from relluna.core.document_memory import Layer0Custodia as Layer0
from relluna.core.document_memory.layer1 import Layer1

router = APIRouter()
templates = Jinja2Templates(directory="relluna/services/test_ui/templates")

UPLOAD_DIR = Path("uploads_test_ui")
UPLOAD_DIR.mkdir(exist_ok=True)

@router.get("/test-ui", response_class=HTMLResponse)
async def test_ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.post("/test-ui/upload", response_class=HTMLResponse)
async def upload_file(request: Request, file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Define media type
    media_type = MediaType.documento
    if file.filename.lower().endswith((".jpg", ".jpeg", ".png")):
        media_type = MediaType.imagem
    elif file.filename.lower().endswith((".mp4", ".mov")):
        media_type = MediaType.video
    elif file.filename.lower().endswith((".mp3", ".wav", ".m4a")):
        media_type = MediaType.audio

    # Criar DocumentMemory
    dm = DocumentMemory(
        layer0=Layer0(
            documentid=file_id,
            contentfingerprint=sha256(file_id.encode()).hexdigest()[:16],
            ingestiontimestamp=datetime.utcnow(),
            ingestionagent="test-ui",
        ),
        layer1=Layer1(
            midia=media_type,
            origem=OriginType.digitalizado,
            artefatos=[
                ArtefatoBruto(
                    uri=str(file_path),
                    nome=file.filename,
                )
            ],
        ),
    )

    # Rodar pipeline
    dm = run_basic_pipeline(dm)
    dm = infer_layer3(dm)
    dm = apply_layer4(dm)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "result": dm,
        },
    )
