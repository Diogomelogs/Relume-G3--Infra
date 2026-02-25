from pathlib import Path
from tests.utils.schema_validator import validate_dm

BASE = Path("tests")
E2E = BASE / "e2e"
DATA = BASE / "data"

FILES = {
    E2E / "conftest.py": '''
import pytest
from fastapi.testclient import TestClient
from relluna.api import app

@pytest.fixture(scope="session")
def client():
    return TestClient(app)
''',

    E2E / "test_image_no_exif.py": '''
def test_image_without_exif_no_false_positive(client):
    with open("tests/data/image_no_exif.jpg", "rb") as f:
        r = client.post("/ingest", files={"file": f})

    assert r.status_code == 200
    docid = r.json()["documentid"]

    r = client.post(f"/extract/{docid}")
    dm = r.json()
    validate_dm(dm)

    assert dm["layer2"] is not None
    assert dm["layer3"] is None
''',

    E2E / "test_pdf_textual.py": '''
def test_pdf_with_text_generates_layer3(client):
    with open("tests/data/pdf_textual.pdf", "rb") as f:
        r = client.post("/ingest", files={"file": f})

    docid = r.json()["documentid"]

    r = client.post(f"/extract/{docid}")
    dm = r.json()

    assert dm["layer2"]["num_paginas"]["valor"] > 0
    assert dm["layer3"] is not None
''',

    E2E / "test_audio_wav.py": '''
def test_audio_generates_layer2(client):
    with open("tests/data/audio.wav", "rb") as f:
        r = client.post("/ingest", files={"file": f})

    docid = r.json()["documentid"]

    r = client.post(f"/extract/{docid}")
    dm = r.json()

    assert dm["layer2"] is not None
    assert "duracao_segundos" in dm["layer2"]
''',

    E2E / "test_infer_without_extract.py": '''
def test_infer_context_without_extract_does_not_create_layer3(client):
    with open("tests/data/image_no_exif.jpg", "rb") as f:
        r = client.post("/ingest", files={"file": f})

    docid = r.json()["documentid"]

    r = client.post(f"/infer_context/{docid}")
    dm = r.json()
    validate_dm(dm)

    assert dm["layer3"] is None
''',

    E2E / "test_heic_blocked.py": '''
def test_heic_blocked_on_ingest(client):
    with open("tests/data/image.heic", "rb") as f:
        r = client.post("/ingest", files={"file": f})

    assert r.status_code == 415
''',
}

PLACEHOLDERS = {
    DATA / "image_no_exif.jpg": b"JPEGPLACEHOLDER",
    DATA / "pdf_textual.pdf": b"%PDF-1.4\\n%PLACEHOLDER",
    DATA / "audio.wav": b"RIFFPLACEHOLDER",
    DATA / "image.heic": b"HEICPLACEHOLDER",
}


def main():
    print("Criando estrutura de testes E2E...")

    for d in (BASE, E2E, DATA):
        d.mkdir(parents=True, exist_ok=True)

    for path, content in FILES.items():
        path.write_text(content.strip() + "\\n", encoding="utf-8")
        print(f"✓ criado {path}")

    for path, content in PLACEHOLDERS.items():
        if not path.exists():
            path.write_bytes(content)
            print(f"✓ criado placeholder {path}")

    print("\\nEstrutura criada.")
    print("⚠️ Substitua os arquivos em tests/data por arquivos reais antes de rodar os testes.")
    print("Depois execute: pytest tests/e2e -v")


if __name__ == "__main__":
    main()
