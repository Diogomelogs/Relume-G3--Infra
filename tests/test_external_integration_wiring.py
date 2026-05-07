from __future__ import annotations

import asyncio
import importlib
from datetime import datetime, timezone

from relluna.core.document_memory import ArtefatoBruto, DocumentMemory, Layer0, Layer1, MediaType, OriginType
from relluna.core.document_memory.layer1 import ArtefatoTipo
from relluna.core.document_memory.layer0 import IntegrityProof
from relluna.infra.blob.client import get_blob_settings
import relluna.infra.mongo_store as mongo_store


def test_blob_settings_accepts_legacy_connection_string(monkeypatch):
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.setenv("AZURE_BLOB_CONNECTION_STRING", "legacy-conn")
    monkeypatch.setenv("AZURE_CONTAINER_RAW", "relluna-raw")
    monkeypatch.delenv("AZURE_BLOB_CONTAINER", raising=False)

    settings = get_blob_settings()

    assert settings.connection_string == "legacy-conn"
    assert settings.container_name == "relluna-raw"


def test_blob_settings_prefers_primary_connection_string(monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "primary-conn")
    monkeypatch.setenv("AZURE_BLOB_CONNECTION_STRING", "legacy-conn")
    monkeypatch.setenv("AZURE_BLOB_CONTAINER", "memories")

    settings = get_blob_settings()

    assert settings.connection_string == "primary-conn"
    assert settings.container_name == "memories"


def test_mongo_store_prefers_mongo_db_env(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.requested = []

        def __getitem__(self, name: str):
            self.requested.append(name)
            return {"db_name": name}

    fake_client = FakeClient()

    monkeypatch.setenv("MONGO_URI", "mongodb://example")
    monkeypatch.setenv("MONGO_DB", "relluna-primary")
    monkeypatch.setenv("MONGO_DB_NAME", "relluna-legacy")
    monkeypatch.setattr(mongo_store, "_client", None)
    monkeypatch.setattr(mongo_store, "_db", None)
    monkeypatch.setattr(mongo_store, "get_mongo_client", lambda: fake_client)

    db = mongo_store.get_database()

    assert db == {"db_name": "relluna-primary"}
    assert fake_client.requested == ["relluna-primary"]


def test_mongo_store_get_ignores_mongo_internal_id(monkeypatch):
    reloaded_mongo_store = importlib.reload(mongo_store)

    class FakeCollection:
        async def find_one(self, query):
            assert query == {"layer0.documentid": "doc-123"}
            return {
                "_id": "mongo-object-id",
                "version": "v0.2.0",
                "layer0": {
                    "documentid": "doc-123",
                    "contentfingerprint": "f" * 64,
                    "ingestiontimestamp": datetime.now(timezone.utc),
                    "ingestionagent": "test",
                    "integrityproofs": [IntegrityProof.local_sha256("f" * 64).model_dump(mode="python")],
                },
                "layer1": {
                    "midia": MediaType.documento.value,
                    "origem": OriginType.digital_nativo.value,
                    "artefatos": [
                        ArtefatoBruto(
                            id="doc-123",
                            tipo=ArtefatoTipo.original,
                            uri="/tmp/doc-123.txt",
                        ).model_dump(mode="python")
                    ],
                },
            }

    monkeypatch.setenv("MONGO_URI", "mongodb://example")
    monkeypatch.setattr(reloaded_mongo_store, "get_collection", lambda: FakeCollection())

    dm = asyncio.run(reloaded_mongo_store.get("doc-123"))

    assert isinstance(dm, DocumentMemory)
    assert dm.layer0.documentid == "doc-123"
