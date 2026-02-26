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

    # Salva o arquivo em disco
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Lê o conteúdo salvo e calcula SHA-256 completo (64 caracteres)
    content = file_path.read_bytes()
    digest = sha256(content).hexdigest()

    # Define media type por extensão
    media_type = MediaType.documento
    fname_lower = file.filename.lower()

    if fname_lower.endswith((".jpg", ".jpeg", ".png")):
        media_type = MediaType.imagem
    elif fname_lower.endswith((".mp4", ".mov")):
        media_type = MediaType.video
    elif fname_lower.endswith((".mp3", ".wav", ".m4a")):
        media_type = MediaType.audio

    now = datetime.utcnow()

    # Criar DocumentMemory com Layer0 e Layer1 consistentes com a API
    dm = DocumentMemory(
        layer0=Layer0(
            documentid=file_id,
            contentfingerprint=digest,
            ingestiontimestamp=now,
            ingestionagent="test-ui",
            integrityproofs=[{"algoritmo": "sha256", "hash": digest}],
            juridicalreadinesslevel=0,
            processingevents=[],
        ),
        layer1=Layer1(
            midia=media_type,
            origem=OriginType.digitalizado,
            artefatos=[
                ArtefatoBruto(
                    id=file_id,
                    tipo="original",
                    uri=str(file_path),
                    nome=file.filename,
                    mimetype=file.content_type,
                    tamanho_bytes=len(content),
                    created_at=now,
                )
            ],
        ),
    )

    # Rodar pipeline básica
    dm = run_basic_pipeline(dm)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "result": dm,
        },
    )
