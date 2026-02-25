from azure.storage.blob import BlobServiceClient
from dataclasses import dataclass
import os


@dataclass
class BlobSettings:
    connection_string: str
    container_name: str


def get_blob_settings() -> BlobSettings:
    return BlobSettings(
        connection_string=os.environ["AZURE_BLOB_CONNECTION_STRING"],
        container_name=os.environ.get("AZURE_BLOB_CONTAINER", "memories"),
    )


def get_blob_service() -> BlobServiceClient:
    settings = get_blob_settings()
    return BlobServiceClient.from_connection_string(
        settings.connection_string
    )
