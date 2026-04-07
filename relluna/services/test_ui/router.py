from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="relluna/services/test_ui/templates")


@router.get("/test-ui", response_class=HTMLResponse)
async def test_ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})