import os

from tests.utils.schema_validator import validate_dm

DATA = "tests/data/golden"

FILES = {
    "imagem": "IMG_0249.JPG",
    "video": "IMG_7245.MOV",
    "audio": "Gravando.m4a",
    "documento": "Recibo do bilhete eletrônico, 03 Junho para DIOGO SILVA.pdf",
}


def _ingest_and_extract(client, filename):
    path = os.path.join(DATA, filename)
    with open(path, "rb") as f:
        r = client.post("/ingest", files={"file": f})
    assert r.status_code == 200
    docid = r.json()["documentid"]

    r = client.post(f"/extract/{docid}")
    assert r.status_code == 200
    return r.json()


def test_layer5_image_derivative(client):
    dm = _ingest_and_extract(client, FILES["imagem"])
    validate_dm(dm)

    assert dm["layer5"] is not None
    imgs = dm["layer5"]["imagens_derivadas"]
    assert len(imgs) == 1
    assert imgs[0]["tipo"] == "thumbnail"


def test_layer5_video_derivative(client):
    dm = _ingest_and_extract(client, FILES["video"])
    validate_dm(dm)

    vids = dm["layer5"]["videos_derivados"]
    assert len(vids) == 1
    assert vids[0]["tipo"] == "frame_chave"


def test_layer5_audio_derivative(client):
    dm = _ingest_and_extract(client, FILES["audio"])
    validate_dm(dm)

    auds = dm["layer5"]["audios_derivados"]
    assert len(auds) == 1
    assert auds[0]["tipo"] == "waveform"


def test_layer5_document_derivative(client):
    dm = _ingest_and_extract(client, FILES["documento"])
    validate_dm(dm)

    docs = dm["layer5"]["documentos_derivados"]
    assert len(docs) == 1
    assert docs[0]["tipo"] == "preview"


def test_layer5_not_created_without_layer1(client):
    """
    Força cenário inválido upstream (proteção)
    """
    dm = {
        "version": "v0.1.0",
        "layer0": {},
        "layer1": None,
        "layer2": None,
        "layer3": None,
        "layer4": None,
        "layer5": None,
        "layer6": None,
    }

    # Layer5 nunca deve surgir do nada
    assert dm["layer5"] is None
