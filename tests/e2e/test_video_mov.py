import os

VIDEO = "IMG_7245.MOV"

def test_video_generates_layer2(client):
    path = os.path.join("tests/data/golden", VIDEO)
    with open(path, "rb") as f:
        r = client.post("/ingest", files={"file": f})

    assert r.status_code == 200
    docid = r.json()["documentid"]

    r = client.post(f"/extract/{docid}")
    dm = r.json()

    assert dm["layer2"] is not None
    assert (
        "duracao_segundos" in dm["layer2"]
        or dm["layer2"].get("entidades_visuais_objetivas")
    )
