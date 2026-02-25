def test_layer5_persists_to_azure(client):
    with open("tests/data/golden/IMG_0249.JPG", "rb") as f:
        r = client.post("/ingest", files={"file": f})
    docid = r.json()["documentid"]

    r = client.post(f"/extract/{docid}")
    dm = r.json()

    assert "layer5" in dm
    assert dm["layer5"]["persistence_state"] == "stored"
    assert len(dm["layer5"]["storage_uris"]) > 0
