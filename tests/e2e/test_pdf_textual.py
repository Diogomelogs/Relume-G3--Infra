import os

PDF = "Recibo do bilhete eletrônico, 03 Junho para DIOGO SILVA.pdf"

def test_pdf_generates_layer2_and_allows_layer3(client):
    path = os.path.join("tests/data/golden", PDF)
    with open(path, "rb") as f:
        r = client.post("/ingest", files={"file": f})

    assert r.status_code == 200
    docid = r.json()["documentid"]

    r = client.post(f"/extract/{docid}")
    dm = r.json()

    assert dm["layer2"]["num_paginas"]["valor"] >= 1
    # Layer3 pode ou não existir dependendo do OCR, mas nunca deve ser falso positivo
    assert "layer3" not in dm or "estimativa_temporal" in dm["layer3"]


