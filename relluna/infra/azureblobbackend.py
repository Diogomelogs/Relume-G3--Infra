import os
from typing import Optional

from relluna.infra.blob.client import get_blob_settings

try:
    # Tenta importar o SDK oficial da Azure
    from azure.storage.blob import BlobServiceClient, ContainerClient  # type: ignore
except ImportError:
    # Em ambientes sem o pacote instalado (ex.: dev/local, CI, container leve),
    # deixamos como None e tratamos isso como "não configurado".
    BlobServiceClient = None  # type: ignore[assignment]
    ContainerClient = None  # type: ignore[assignment]


class AzureBlobBackend:
    """
    Backend mínimo para Azure Blob Storage.

    Comportamento:
    - Se o pacote azure-storage-blob NÃO estiver instalado ou a connection string
      não estiver definida → is_configured = False, ping() = False.
    - upload() lança RuntimeError se chamado sem estar configurado.
    """

    def __init__(self, conn_str: Optional[str] = None) -> None:
        resolved_conn_str = conn_str
        if resolved_conn_str is None:
            try:
                resolved_conn_str = get_blob_settings().connection_string
            except RuntimeError:
                resolved_conn_str = None
        self._conn_str = resolved_conn_str
        self._client = None

        if self._conn_str and BlobServiceClient is not None:
            self._client = BlobServiceClient.from_connection_string(self._conn_str)

    @property
    def is_configured(self) -> bool:
        """Indica se temos SDK + connection string configurados."""
        return self._client is not None

    def _get_container_client(self, container: str):
        if not self._client:
            raise RuntimeError(
                "Azure Blob backend not configured "
                "(missing SDK or AZURE_STORAGE_CONNECTION_STRING)"
            )
        return self._client.get_container_client(container)

    def upload(self, container: str, blob_path: str, data: bytes) -> str:
        """
        Faz upload de um blob e retorna a URL.
        """
        container_client = self._get_container_client(container)
        try:
            container_client.create_container()
        except Exception:
            pass
        blob = container_client.get_blob_client(blob_path)
        blob.upload_blob(data, overwrite=True)
        return blob.url

    def download(self, container: str, blob_path: str) -> bytes:
        container_client = self._get_container_client(container)
        blob = container_client.get_blob_client(blob_path)
        return blob.download_blob().readall()

    def delete(self, container: str, blob_path: str) -> None:
        container_client = self._get_container_client(container)
        blob = container_client.get_blob_client(blob_path)
        blob.delete_blob(delete_snapshots="include")

    def ping(self) -> bool:
        """
        Verifica se conseguimos falar com o serviço.
        Uso típico: health check.
        """
        if not self._client:
            # Não configurado neste ambiente (sem SDK ou sem connection string).
            return False

        try:
            _ = list(self._client.list_containers(name_starts_with=None))[:1]
            return True
        except Exception:
            return False
