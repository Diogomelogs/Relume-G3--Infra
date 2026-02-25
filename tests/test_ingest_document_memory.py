import io
from datetime import datetime

from fastapi.testclient import TestClient
from pydantic_core import ValidationError

from relluna.services.ingestion.api import app
from relluna.core.document_memory import DocumentMemory


def test_ingest_returns_valid_document_memory():
    fake_image = io.BytesIO(b"\xFF\xD8\xFF\xE0" + b"0" * 1024)
    fake_image.name = "teste.jpg"

    # cria e fecha o client dentro do teste → evita problema de event loop fechado
    with TestClient(app) as client:
        # 1) /ingest → só id + hash
        resp_ingest = client.post(
            "/ingest",
            files={"file": ("teste.jpg", fake_image, "image/jpeg")},
        )
        assert resp_ingest.status_code == 200, resp_ingest.text

        ingest_data = resp_ingest.json()
        assert "documentid" in ingest_data
        assert "hash" in ingest_data

        documentid = ingest_data["documentid"]

        # 2) /documents/{id} → DM completo
        resp_dm = client.get(f"/documents/{documentid}")
        assert resp_dm.status_code == 200, resp_dm.text

        dm_data = resp_dm.json()
        print("\nDM bruto recebido da API (/documents/{id}):")
        print(dm_data)

        # 3) Validação contra o modelo
        try:
            dm = DocumentMemory.model_validate(dm_data)
        except ValidationError as e:
            print("\nERROS DE VALIDAÇÃO DO DOCUMENTMEMORY:")
            for err in e.errors():
                print(err)
            raise

        # 4) Asserções básicas
        assert dm.version == "v0.1.0"
        assert isinstance(dm.layer0.ingestiontimestamp, datetime)
        assert dm.layer0.documentid == documentid
        assert dm.layer0.contentfingerprint
        assert dm.layer0.ingestionagent != ""

        assert dm.layer1.midia.value == "imagem"
        assert len(dm.layer1.artefatos) >= 1

def test_ingest_with_nsfw_enabled(client):
    fake_image = io.BytesIO(b"\xFF\xD8\xFF\xE0" + b"0" * 1024)
    fake_image.name = "safe.jpg"

    resp = client.post(
        "/ingest",
        files={"file": ("safe.jpg", fake_image, "image/jpeg")},
    )

    assert resp.status_code == 200