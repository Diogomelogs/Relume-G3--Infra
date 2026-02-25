from pathlib import Path
from relluna.infra.blob import AzureBlobArtefactStore


def test_blob_upload_and_download(tmp_path):
    store = AzureBlobArtefactStore()

    src = tmp_path / "file.txt"
    src.write_text("relluna")

    artefact_id = "test-artefact-123"
    blob_path = store.upload(src, artefact_id)

    assert "artefacts/" in blob_path

    dest = tmp_path / "out.txt"
    store.download(artefact_id, dest)

    assert dest.read_text() == "relluna"
