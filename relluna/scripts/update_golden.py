# scripts/update_golden.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi.testclient import TestClient

from relluna.services.ingestion.api import app
from tests.test_pipeline_e2e_layers_0_3 import MEDIA_DIR, GOLDEN_DIR, normalize_dm_for_comparison  # ajuste o import se necessário


E2E_CASES = {
    "e2e_image_exif": (
        "image_exif.jpg",
        "dm_image_exif_complete.json",
        "image/jpeg",
    ),
    "e2e_image_analog": (
        "image_analog.jpg",
        "dm_image_analog_no_exif.json",
        "image/jpeg",
    ),
    "e2e_pdf_simple": (
        "simple.pdf",
        "dm_pdf_simple.json",
        "application/pdf",
    ),
    "e2e_audio_wav": (
        "audio.wav",
        "dm_audio_wav.json",
        "audio/wav",
    ),
}


def regenerate_golden(case_name: str) -> None:
    media_filename, golden_filename, content_type = E2E_CASES[case_name]

    media_path = MEDIA_DIR / media_filename
    golden_path = GOLDEN_DIR / golden_filename

    with TestClient(app) as client:
        # 1) /ingest
        with media_path.open("rb") as f:
            resp = client.post(
                "/ingest",
                files={"file": (media_filename, f, content_type)},
            )
        resp.raise_for_status()
        documentid = resp.json()["documentid"]

        # 2) /extract/{id}
        resp = client.post(f"/extract/{documentid}")
        resp.raise_for_status()

        # 3) /infer_context/{id}
        resp = client.post(f"/infer_context/{documentid}")
        resp.raise_for_status()

        # 4) GET /documents/{id}
        resp = client.get(f"/documents/{documentid}")
        resp.raise_for_status()
        live_dm = resp.json()

    norm_live = normalize_dm_for_comparison(live_dm)

    # Salva o golden normalizado
    golden_path.write_text(json.dumps(norm_live, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Golden atualizado: {golden_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Atualiza goldens E2E a partir do pipeline real.")
    parser.add_argument(
        "case",
        choices=list(E2E_CASES.keys()) + ["all"],
        help="Nome do caso E2E ou 'all'",
    )
    args = parser.parse_args()

    if args.case == "all":
        for name in E2E_CASES:
            regenerate_golden(name)
    else:
        regenerate_golden(args.case)
