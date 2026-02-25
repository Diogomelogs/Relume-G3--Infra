import io
from fastapi.testclient import TestClient

from relluna.services.ingestion.api import app
from relluna.core.document_memory import DocumentMemory, ConfidenceState


def test_infer_context_populates_layer3_for_image():
    fake_image = io.BytesIO(b"\xFF\xD8\xFF\xE0" + b"0" * 1024)
    fake_image.name = "teste.jpg"

    with TestClient(app) as client:
        # 1) Ingest
        resp_ingest = client.post(
            "/ingest",
            files={"file": ("teste.jpg", fake_image, "image/jpeg")},
        )
        assert resp_ingest.status_code == 200
        documentid = resp_ingest.json()["documentid"]

        # 2) Extrai Layer2
        resp_extract = client.post(f"/extract/{documentid}")
        assert resp_extract.status_code == 200

        # 3) Inferência de contexto (Layer3)
        resp_infer = client.post(f"/infer_context/{documentid}")
        assert resp_infer.status_code == 200
        dm_data = resp_infer.json()

        dm = DocumentMemory.model_validate(dm_data)

        # Layer3 deve existir
        assert dm.layer3 is not None

        # Para imagem simples, tipo_evento inferido não-vazio
        assert dm.layer3.tipo_evento is not None
        assert dm.layer3.tipo_evento.estado == ConfidenceState.inferido
        assert dm.layer3.tipo_evento.valor in {"imagem", "registro_video", "registro_audio", "documento"}
