from datetime import datetime
from relluna.core.document_memory import (
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    ArtefatoBruto,
    MediaType,
    OriginType,
)
from relluna.core.basic_pipeline import run_basic_pipeline
from relluna.infra.mongo import MongoDocumentStore
from relluna.infra.blob import AzureBlobArtefactStore


def ingest_file(
    *,
    file_bytes: bytes,
    filename: str,
    media_type: MediaType,
    origin: OriginType,
    ingestion_agent: str = "api",
) -> DocumentMemory:
    # 1. Upload blob
    blob_store = AzureBlobArtefactStore()
    blob_uri = blob_store.upload_bytes(
        content=file_bytes,
        filename=filename,
    )

    # 2. Criar DocumentMemory (Layer0 + Layer1)
    dm = DocumentMemory(
        layer0=Layer0Custodia(
            documentid=DocumentMemory.generate_id(),
            contentfingerprint=DocumentMemory.hash_bytes(file_bytes),
            ingestiontimestamp=datetime.utcnow(),
            ingestionagent=ingestion_agent,
        ),
        layer1=Layer1Artefatos(
            midia=media_type,
            origem=origin,
            artefatos=[
                ArtefatoBruto(
                    id="original",
                    tipo="original",
                    uri=blob_uri,
                )
            ],
        ),
    )

    # 3. Pipeline mínimo
    dm = run_basic_pipeline(dm)

    # 4. Persistir no Mongo
    store = MongoDocumentStore()
    store.save(dm)

    return dm
