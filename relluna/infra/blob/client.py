from azure.storage.blob import BlobServiceClient
from dataclasses import dataclass

from relluna.infra.secrets import get_secret


@dataclass
class BlobSettings:
    connection_string: str
    container_name: str


def get_blob_settings() -> BlobSettings:
    connection_string = (
        get_secret("AZURE_STORAGE_CONNECTION_STRING", default="")
        or get_secret("AZURE_BLOB_CONNECTION_STRING", default="")
    )
    if not connection_string:
        raise RuntimeError(
            "Missing env var: AZURE_STORAGE_CONNECTION_STRING "
            "(or legacy AZURE_BLOB_CONNECTION_STRING)"
        )

    container_name = (
        get_secret("AZURE_BLOB_CONTAINER", default="")
        or get_secret("AZURE_CONTAINER_RAW", default="")
        or "memories"
    )

    return BlobSettings(
        connection_string=connection_string,
        container_name=container_name,
    )


def get_blob_service() -> BlobServiceClient:
    settings = get_blob_settings()
    return BlobServiceClient.from_connection_string(
        settings.connection_string
    )
