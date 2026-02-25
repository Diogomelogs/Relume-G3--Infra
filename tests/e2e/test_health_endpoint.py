from fastapi.testclient import TestClient

from relluna.services.ingestion.api import app


client = TestClient(app)


def test_health_endpoint_basic_contract():
    resp = client.get("/health")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] in {"ok", "degraded", "error"}
    assert "version" in data
    assert isinstance(data["services"], list)

    names = {s["name"] for s in data["services"]}
    assert {"api", "mongo", "blob"}.issubset(names)
