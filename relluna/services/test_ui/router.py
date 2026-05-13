from pathlib import Path
import mimetypes

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

router = APIRouter()

FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"
FRONTEND_INDEX = FRONTEND_DIR / "index.html"
LEGACY_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(LEGACY_TEMPLATE_DIR))


@router.get("/test-ui-lab", response_class=HTMLResponse)
async def test_ui_lab(request: Request):
    template_path = LEGACY_TEMPLATE_DIR / "index.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Legacy test UI template not found")
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/demo")
async def demo_index():
    if not FRONTEND_INDEX.exists():
        raise HTTPException(status_code=404, detail="Demo frontend not found")
    return Response(content=FRONTEND_INDEX.read_bytes(), media_type="text/html; charset=utf-8")


@router.get("/demo/{asset_path:path}")
async def demo_asset(asset_path: str):
    asset = (FRONTEND_DIR / asset_path).resolve()
    try:
        asset.relative_to(FRONTEND_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Asset not found") from exc

    if not asset.exists() or not asset.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")

    media_type, _ = mimetypes.guess_type(asset.name)
    return Response(
        content=asset.read_bytes(),
        media_type=media_type or "application/octet-stream",
    )
