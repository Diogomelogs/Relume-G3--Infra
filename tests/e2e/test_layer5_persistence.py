def test_layer5_does_not_claim_real_persistence_without_storage_backend(client):
    with open("tests/data/golden/IMG_0249.JPG", "rb") as f:
        r = client.post("/ingest", files={"file": f})
    docid = r.json()["documentid"]

    r = client.post(f"/extract/{docid}")
    dm = r.json()

    assert "layer5" in dm
    assert dm["layer5"]["persistence_state"] == "placeholder_not_persisted"
    assert dm["layer5"]["storage_uris"] == []
