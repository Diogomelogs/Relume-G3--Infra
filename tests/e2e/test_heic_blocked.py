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
