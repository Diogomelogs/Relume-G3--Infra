from fastapi.testclient import TestClient

from relluna.services.ingestion.api import app

client = TestClient(app)


def test_narrative_endpoint_returns_text_for_image_exif():
    # Ingesta uma imagem golden
    with open("tests/data/golden/IMG_0249.JPG", "rb") as f:
        r = client.post("/ingest", files={"file": f})
    docid = r.json()["documentid"]

    # Garante Layers 2–4 preenchidas
    client.post(f"/extract/{docid}")
    client.post(f"/infer_context/{docid}")

    # Chama narrativa
    r = client.get(f"/documents/{docid}/narrative")
    assert r.status_code == 200

    data = r.json()
    assert data["documentid"] == docid
    assert isinstance(data["narrative"], str)
    assert len(data["narrative"].strip()) > 0
