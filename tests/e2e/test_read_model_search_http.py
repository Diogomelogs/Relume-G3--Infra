from fastapi.testclient import TestClient
from relluna.services.ingestion.api import app

client = TestClient(app)


def test_read_model_search_http_works_basic():
    # injeta pelo menos 1 documento (só pra garantir fluxo de ingest/extract)
    with open("tests/data/golden/IMG_0249.JPG", "rb") as f:
        r = client.post("/ingest", files={"file": f})
    docid = r.json()["documentid"]

    client.post(f"/extract/{docid}")

    # aqui só validamos que o endpoint responde 200,
    # sem usar q (evita $text e índice obrigatório)
    r = client.get("/read-model/documents", params={"limit": 10})
    assert r.status_code == 200
