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

    @property
    def container_name(self) -> str:
        return self._settings.container_name

    def blob_path_for(self, artefact_id: str) -> str:
        return artefact_blob_path(artefact_id)

    def blob_url_for(self, artefact_id: str) -> str:
        blob_path = self.blob_path_for(artefact_id)
        return self._container.get_blob_client(blob_path).url

    def upload_bytes(self, content: bytes, artefact_id: str) -> str:
        blob_path = self.blob_path_for(artefact_id)
        blob = self._container.get_blob_client(blob_path)
        blob.upload_blob(content, overwrite=True)
        return blob_path

    def upload(self, local_path: Path, artefact_id: str) -> str:
        blob_path = self.blob_path_for(artefact_id)
        blob = self._container.get_blob_client(blob_path)

        with open(local_path, "rb") as f:
            blob.upload_blob(f, overwrite=True)

        return blob_path

    def download(self, artefact_id: str, dest: Path) -> None:
        blob_path = self.blob_path_for(artefact_id)
        dest.write_bytes(self.download_bytes(artefact_id))

    def download_bytes(self, artefact_id: str) -> bytes:
        blob_path = self.blob_path_for(artefact_id)
        blob = self._container.get_blob_client(blob_path)
        return blob.download_blob().readall()

    def delete(self, artefact_id: str) -> None:
        blob_path = self.blob_path_for(artefact_id)
        blob = self._container.get_blob_client(blob_path)
        blob.delete_blob(delete_snapshots="include")
