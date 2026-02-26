# tools/regenerate_goldens_v0_2_0.py
from __future__ import annotations

import json
from pathlib import Path
from fastapi.testclient import TestClient

from relluna.services.ingestion.api import app

MEDIA_DIR = Path("tests/data/media")
GOLDEN_DIR = Path("tests/data/golden")

CASES = [
    ("image_exif.jpg", "dm_image_exif_complete.json", "image/jpeg"),
    ("image_analog.jpg", "dm_image_analog_no_exif.json", "image/jpeg"),
    ("simple.pdf", "dm_pdf_simple.json", "application/pdf"),
    ("audio.wav", "dm_audio_wav.json", "audio/wav"),
]

def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    client = TestClient(app)

    for media_filename, golden_filename, content_type in CASES:
        media_path = MEDIA_DIR / media_filename
        if not media_path.exists():
            print(f"[SKIP] media não encontrada: {media_path}")
            continue

        # 1) ingest
        with media_path.open("rb") as f:
            resp = client.post("/ingest", files={"file": (media_filename, f, content_type)})
        resp.raise_for_status()
        documentid = resp.json()["documentid"]

        # 2) extract
        resp = client.post(f"/extract/{documentid}")
        resp.raise_for_status()

        # 3) infer_context (gera layer3 + layer4)
        resp = client.post(f"/infer_context/{documentid}")
        resp.raise_for_status()

        # 4) get final
        resp = client.get(f"/documents/{documentid}")
        resp.raise_for_status()
        dm_contract = resp.json()  # já serializável (dict “contrato”)

        (GOLDEN_DIR / golden_filename).write_text(
            json.dumps(dm_contract, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[OK] golden atualizado: {golden_filename}")

if __name__ == "__main__":
    main()