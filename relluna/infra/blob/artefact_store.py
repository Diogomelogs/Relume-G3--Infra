from pathlib import Path
from relluna.infra.blob.client import get_blob_service, get_blob_settings
from relluna.infra.blob.paths import artefact_blob_path


class AzureBlobArtefactStore:
    def __init__(self):
        self._service = get_blob_service()
        self._settings = get_blob_settings()
        self._container = self._service.get_container_client(
            self._settings.container_name
        )

        # garante que o container existe
        try:
            self._container.create_container()
        except Exception:
            pass  # já existe


    def upload(self, local_path: Path, artefact_id: str) -> str:
        blob_path = artefact_blob_path(artefact_id)
        blob = self._container.get_blob_client(blob_path)

        with open(local_path, "rb") as f:
            blob.upload_blob(f, overwrite=True)

        return blob_path

    def download(self, artefact_id: str, dest: Path) -> None:
        blob_path = artefact_blob_path(artefact_id)
        blob = self._container.get_blob_client(blob_path)

        with open(dest, "wb") as f:
            f.write(blob.download_blob().readall())
