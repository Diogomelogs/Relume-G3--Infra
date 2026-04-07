from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.layer0 import (
    CustodyEvent,
    IntegrityProof,
    Layer0,
    ProcessingEvent,
    VersionEdge,
)
from relluna.core.document_memory.layer1 import (
    ArtefatoBruto,
    ArtefatoTipo,
    Layer1,
    MediaType,
    OriginType,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_valid_layer0() -> Layer0:
    return Layer0(
        documentid="doc-001",
        contentfingerprint="a" * 64,
        fingerprint_algorithm="sha256",
        ingestiontimestamp=_utc_now(),
        ingestionagent="api",
        original_filename="contrato.pdf",
        mimetype="application/pdf",
        size_bytes=123456,
        authenticitystate="preservado_com_hash_local",
        juridicalreadinesslevel=0,
        integrityproofs=[
            IntegrityProof.local_sha256("a" * 64),
        ],
        custodychain=[
            {
                "timestamp": _utc_now().isoformat(),
                "etapa": "ingest",
                "agente": "api",
                "acao": "store_original",
                "destino_uri": "/tmp/contrato.pdf",
                "detalhes": {"filename": "contrato.pdf"},
            }
        ],
        processingevents=[
            {
                "timestamp": _utc_now().isoformat(),
                "etapa": "ingest",
                "engine": "api",
                "status": "success",
                "detalhes": {"media_type_detected": "documento"},
            }
        ],
        versiongraph=[],
    )


def make_valid_layer1() -> Layer1:
    return Layer1(
        midia=MediaType.documento,
        origem=OriginType.digital_nativo,
        artefatos=[
            ArtefatoBruto(
                id="doc-001",
                tipo=ArtefatoTipo.original,
                uri="/tmp/contrato.pdf",
                nome="contrato.pdf",
                mimetype="application/pdf",
                tamanho_bytes=123456,
                hash_sha256="b" * 64,
                metadados_nativos={"upload_content_type": "application/pdf"},
            )
        ],
    )


def test_layer0_valid_contract():
    layer0 = make_valid_layer0()

    assert layer0.documentid == "doc-001"
    assert layer0.contentfingerprint == "a" * 64
    assert layer0.fingerprint_algorithm == "sha256"
    assert layer0.ingestionagent == "api"
    assert layer0.original_filename == "contrato.pdf"
    assert layer0.mimetype == "application/pdf"
    assert layer0.size_bytes == 123456
    assert layer0.authenticitystate == "preservado_com_hash_local"
    assert layer0.juridicalreadinesslevel == 0

    assert len(layer0.integrityproofs) == 1
    assert isinstance(layer0.integrityproofs[0], IntegrityProof)
    assert layer0.integrityproofs[0].payload["hash"] == "a" * 64

    assert len(layer0.custodychain) == 1
    assert isinstance(layer0.custodychain[0], CustodyEvent)
    assert layer0.custodychain[0].etapa == "ingest"

    assert len(layer0.processingevents) == 1
    assert isinstance(layer0.processingevents[0], ProcessingEvent)
    assert layer0.processingevents[0].engine == "api"


def test_layer1_valid_contract():
    layer1 = make_valid_layer1()

    assert layer1.midia == MediaType.documento
    assert layer1.origem == OriginType.digital_nativo
    assert len(layer1.artefatos) == 1

    artifact = layer1.artefatos[0]
    assert artifact.tipo == ArtefatoTipo.original
    assert artifact.uri == "/tmp/contrato.pdf"
    assert artifact.nome == "contrato.pdf"
    assert artifact.mimetype == "application/pdf"
    assert artifact.tamanho_bytes == 123456
    assert artifact.hash_sha256 == "b" * 64
    assert artifact.fingerprint_algorithm == "sha256"


def test_documentmemory_with_layers_0_and_1_only():
    dm = DocumentMemory(
        version="v0.2.0",
        layer0=make_valid_layer0(),
        layer1=make_valid_layer1(),
    )

    dumped = dm.model_dump()

    assert dm.version == "v0.2.0"
    assert dumped["layer0"]["documentid"] == "doc-001"
    assert dumped["layer1"]["midia"] == MediaType.documento
    assert dumped["layer1"]["artefatos"][0]["tipo"] == ArtefatoTipo.original


def test_layer0_rejects_invalid_contentfingerprint():
    with pytest.raises(ValidationError) as exc:
        Layer0(
            documentid="doc-invalid",
            contentfingerprint="123",
            ingestionagent="api",
        )

    assert "contentfingerprint" in str(exc.value)


def test_layer0_rejects_naive_ingestiontimestamp():
    with pytest.raises(ValidationError) as exc:
        Layer0(
            documentid="doc-invalid",
            contentfingerprint="a" * 64,
            ingestiontimestamp=datetime.now(),
            ingestionagent="api",
        )

    assert "ingestiontimestamp" in str(exc.value)


def test_layer1_rejects_empty_artefatos():
    with pytest.raises(ValidationError) as exc:
        Layer1(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[],
        )

    assert "artefatos" in str(exc.value)


def test_layer1_rejects_when_no_original_artifact_exists():
    with pytest.raises(ValidationError) as exc:
        Layer1(
            midia=MediaType.documento,
            origem=OriginType.digital_nativo,
            artefatos=[
                ArtefatoBruto(
                    id="preview-001",
                    tipo=ArtefatoTipo.preview,
                    uri="/tmp/preview.png",
                    nome="preview.png",
                    mimetype="image/png",
                    tamanho_bytes=2048,
                    hash_sha256="c" * 64,
                )
            ],
        )

    assert "tipo=original" in str(exc.value)


def test_layer1_rejects_invalid_artifact_sha256():
    with pytest.raises(ValidationError) as exc:
        ArtefatoBruto(
            id="doc-001",
            tipo=ArtefatoTipo.original,
            uri="/tmp/contrato.pdf",
            hash_sha256="bad-hash",
        )

    assert "hash_sha256" in str(exc.value)


def test_layer0_accepts_legacy_dict_processingevents_and_normalizes():
    layer0 = Layer0(
        documentid="doc-legacy-1",
        contentfingerprint="a" * 64,
        ingestionagent="api",
        processingevents=[
            {
                "timestamp": _utc_now().isoformat(),
                "etapa": "ingest",
                "engine": "api",
            }
        ],
    )

    assert len(layer0.processingevents) == 1
    assert isinstance(layer0.processingevents[0], ProcessingEvent)
    assert layer0.processingevents[0].status == "success"
    assert layer0.processingevents[0].detalhes == {}


def test_layer0_accepts_typed_events_and_runtime_append():
    layer0 = Layer0(
        documentid="doc-typed-1",
        contentfingerprint="a" * 64,
        ingestionagent="api",
        custodychain=[
            CustodyEvent(
                etapa="ingest",
                agente="api",
                acao="store_original",
                destino_uri="/tmp/doc.pdf",
            )
        ],
        processingevents=[
            ProcessingEvent(
                etapa="ingest",
                engine="api",
            )
        ],
        versiongraph=[
            VersionEdge(
                from_artifact_id="a1",
                to_artifact_id="a2",
                relation="derived_from",
            )
        ],
        integrityproofs=[IntegrityProof.local_sha256("a" * 64)],
    )

    layer0.processingevents.append(
        ProcessingEvent(
            etapa="extract_basic",
            engine="deterministic_extractors.basic",
            status="success",
            detalhes={},
        )
    )

    assert isinstance(layer0.custodychain[0], CustodyEvent)
    assert isinstance(layer0.processingevents[0], ProcessingEvent)
    assert isinstance(layer0.versiongraph[0], VersionEdge)
    assert len(layer0.processingevents) == 2
    assert layer0.processingevents[-1].etapa == "extract_basic"


def test_layer0_accepts_legacy_dict_custodychain_and_versiongraph():
    layer0 = Layer0(
        documentid="doc-legacy-2",
        contentfingerprint="b" * 64,
        ingestionagent="api",
        custodychain=[
            {
                "timestamp": _utc_now().isoformat(),
                "etapa": "ingest",
                "agente": "api",
                "acao": "store_original",
                "destino_uri": "/tmp/doc.pdf",
                "detalhes": {},
            }
        ],
        versiongraph=[
            {
                "timestamp": _utc_now().isoformat(),
                "from_artifact_id": "orig",
                "to_artifact_id": "norm",
                "relation": "normalized_from",
                "details": {},
            }
        ],
    )

    assert isinstance(layer0.custodychain[0], CustodyEvent)
    assert isinstance(layer0.versiongraph[0], VersionEdge)


def test_documentmemory_serializes_layers_0_and_1():
    dm = DocumentMemory(
        version="v0.2.0",
        layer0=make_valid_layer0(),
        layer1=make_valid_layer1(),
    )

    payload = dm.model_dump_json()

    assert "doc-001" in payload
    assert "contrato.pdf" in payload
    assert "application/pdf" in payload