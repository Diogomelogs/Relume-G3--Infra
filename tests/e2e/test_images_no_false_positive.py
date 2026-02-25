import os
from tests.utils.schema_validator import validate_dm

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
        assert "layer3" not in dm

