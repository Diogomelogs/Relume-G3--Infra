from pathlib import Path
from tests.utils.schema_validator import validate_dm

BASE = Path("tests")
E2E = BASE / "e2e"
GOLDEN = BASE / "data" / "golden"

TESTS = {
    E2E / "conftest.py": '''
import pytest
from fastapi.testclient import TestClient
from relluna.api import app

@pytest.fixture(scope="session")
def client():
    return TestClient(app)
''',

    E2E / "test_images_no_false_positive.py": '''
import os

IMAGES = [
    "IMG_0249.JPG",
    "IMG_0297.JPG",
    "IMG_7367.JPG",
]

def test_images_without_false_positive(client):
    for name in IMAGES:
        path = os.path.join("tests/data/golden", name)
        with open(path, "rb") as f:
            r = client.post("/ingest", files={"file": f})
        assert r.status_code == 200
        docid = r.json()["documentid"]

        r = client.post(f"/extract/{docid}")
        dm = r.json()
        validate_dm(dm)

        assert dm["layer2"] is not None
        assert dm["layer3"] is None
''',

    E2E / "test_heic_blocked.py": '''
import os
import pytest

HEICS = [
    "IMG_0770.HEIC",
    "IMG_7599.HEIC",
]

def test_heic_requires_normalization(client):
    for name in HEICS:
        path = os.path.join("tests/data/golden", name)
        with open(path, "rb") as f:
            r = client.post("/ingest", files={"file": f})

        assert r.status_code == 415
''',

    E2E / "test_pdf_textual.py": '''
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
    if "layer3" in dm:
    # se existir, deve ser semanticamente válida
    assert "estimativa_temporal" in dm["layer3"]
''',

    E2E / "test_audio_m4a.py": '''
import os

AUDIO = "Gravando.m4a"

def test_audio_generates_layer2(client):
    path = os.path.join("tests/data/golden", AUDIO)
    with open(path, "rb") as f:
        r = client.post("/ingest", files={"file": f})

    assert r.status_code == 200
    docid = r.json()["documentid"]

    r = client.post(f"/extract/{docid}")
    dm = r.json()

    assert dm["layer2"] is not None
    assert "duracao_segundos" in dm["layer2"]
''',

    E2E / "test_video_mov.py": '''
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
''',
}


def main():
    print("Criando testes E2E a partir dos arquivos golden...")

    E2E.mkdir(parents=True, exist_ok=True)

    for path, content in TESTS.items():
        path.write_text(content.strip() + "\n", encoding="utf-8")
        print(f"✓ criado {path}")

    print("\nPronto.")
    print("Execute: pytest tests/e2e -v")


if __name__ == "__main__":
    main()
