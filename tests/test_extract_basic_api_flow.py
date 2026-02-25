import io
from fastapi.testclient import TestClient

from relluna.services.ingestion.api import app
from relluna.core.document_memory import DocumentMemory, ConfidenceState


def test_extract_basic_via_api_populates_layer2_for_image():
    fake_image = io.BytesIO(b"\xFF\xD8\xFF\xE0" + b"0" * 1024)
    fake_image.name = "teste.jpg"

    with TestClient(app) as client:
        resp_ingest = client.post(
            "/ingest",
            files={"file": ("teste.jpg", fake_image, "image/jpeg")},
        )
        assert resp_ingest.status_code == 200
        documentid = resp_ingest.json()["documentid"]

        resp_extract = client.post(f"/extract/{documentid}")
        assert resp_extract.status_code == 200

        resp_dm = client.get(f"/documents/{documentid}")
        assert resp_dm.status_code == 200
        dm = DocumentMemory.model_validate(resp_dm.json())

        assert dm.layer2 is not None
        assert dm.layer2.largura_px is not None
        assert dm.layer2.largura_px.estado in {
            ConfidenceState.confirmado,
            ConfidenceState.insuficiente,
        }
