from azure.storage.blob import BlobServiceClient
from dataclasses import dataclass
import os


@dataclass
class BlobSettings:
    connection_string: str
    container_name: str


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def get_blob_settings() -> BlobSettings:
    connection_string = _first_env(
        "AZURE_STORAGE_CONNECTION_STRING",
        "AZURE_BLOB_CONNECTION_STRING",
    )
    if not connection_string:
        raise RuntimeError(
            "Missing env var: AZURE_STORAGE_CONNECTION_STRING "
            "(or legacy AZURE_BLOB_CONNECTION_STRING)"
        )

    return BlobSettings(
        connection_string=connection_string,
        container_name=(
            _first_env(
                "AZURE_BLOB_CONTAINER",
                "AZURE_CONTAINER_RAW",
            )
            or "memories"
        ),
    )


def get_blob_service() -> BlobServiceClient:
    settings = get_blob_settings()
    return BlobServiceClient.from_connection_string(
        settings.connection_string
    )
