def test_layer5_exposes_local_document_memory_persistence_contract(client):
    with open("tests/data/golden/IMG_0249.JPG", "rb") as f:
        r = client.post("/ingest", files={"file": f})
    docid = r.json()["documentid"]

    client.post(f"/extract/{docid}")
    r = client.post(f"/infer_context/{docid}")
    dm = r.json()

    assert "layer5" in dm
    assert dm["layer5"]["persistence_state"] == "stored"
    assert len(dm["layer5"]["storage_uris"]) == 3
