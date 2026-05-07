from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import List, Optional, Callable, Awaitable
from uuid import uuid4
import json
import os
import traceback
from time import perf_counter

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from relluna.core.contracts.mappers import to_contract
from relluna.core.document_memory import (
    ArtefatoBruto,
    DocumentMemory,
    Layer0,
    Layer1,
    MediaType,
    OriginType,
)
from relluna.core.document_memory.layer0 import CustodyEvent, IntegrityProof, ProcessingEvent
from relluna.core.document_memory.layer1 import ArtefatoTipo
from relluna.core.document_memory.layer4_canonical import Layer4SemanticNormalization
from relluna.infra.blob import AzureBlobArtefactStore
from relluna.infra import mongo_store
from relluna.infra.azureblobbackend import AzureBlobBackend
from relluna.infra.mongo.client import get_db
from relluna.services.content_safety.nsfw import check_image_nsfw
from relluna.services.context_inference.basic import infer_layer3
from relluna.services.correlation.layer4 import apply_layer4
from relluna.services.derivatives.layer5 import apply_layer5
from relluna.services.deterministic_extractors.basic import extract_basic
from relluna.services.deterministic_extractors.timeline_seed_v2 import seed_timeline_v2
from relluna.services.entities.entities_canonical_v1 import apply_entities_canonical_v1
from relluna.services.forensics.layer6 import generate_factual_narrative
from relluna.services.legal.legal_pipeline import apply_legal_extraction
from relluna.services.observability import append_processing_event, elapsed_ms, sanitize_processing_details
from relluna.services.orchestration.decision import (
    ProcessingDecision,
    build_escalation_details,
    build_processing_decision_details,
    decide_processing_mode,
    needs_escalation_after_extract,
)
from relluna.services.orchestration.preflight import (
    PreflightSignals,
    collect_preflight_signals,
)
from relluna.services.page_extraction.page_pipeline import apply_page_analysis
from relluna.services.pdf_decomposition.decompose_pdf import decompose_pdf_into_subdocuments
from relluna.services.read_model import documents_router
from relluna.services.read_model.endpoints import router as read_model_router
from relluna.services.read_model.case_builder import build_document_case_read_model
from relluna.services.read_model.projector import persist_document_read_model
from relluna.services.read_model.timeline_builder import build_document_timeline_read_model
from relluna.services.test_ui.router import router as test_ui_router
from relluna.services.transcription.asr import apply_transcription_to_layer2


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


BASE_DIR = Path(__file__).resolve().parents[3]
UPLOAD_DIR = BASE_DIR / ".uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

API_VERSION = "v0.2.0"
DOCUMENT_MEMORY_VERSION = "v0.2.0"
_LOCAL_FILE_STORAGE_STATE = "local_file_persisted"
_LOCAL_FILE_STORAGE_KIND = "local_file"

USE_ADAPTIVE_PIPELINE = True

app = FastAPI(title="Relluna API", version=API_VERSION)
app.include_router(read_model_router)
app.include_router(test_ui_router)
app.include_router(documents_router)


class ServiceStatus(BaseModel):
    name: str
    status: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    services: List[ServiceStatus]


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    services: List[ServiceStatus] = [ServiceStatus(name="api", status="ok")]

    mongo_status = "ok"
    mongo_detail: Optional[str] = None
    try:
        db = get_db()
        db.command("ping")
    except Exception as exc:
        mongo_status = "error"
        mongo_detail = str(exc)

    services.append(ServiceStatus(name="mongo", status=mongo_status, detail=mongo_detail))

    blob_backend = AzureBlobBackend()
    if not blob_backend.is_configured:
        services.append(
            ServiceStatus(
                name="blob",
                status="degraded",
                detail=(
                    "Blob backend not configured "
                    "(AZURE_STORAGE_CONNECTION_STRING or AZURE_BLOB_CONNECTION_STRING)"
                ),
            )
        )
    else:
        if blob_backend.ping():
            services.append(ServiceStatus(name="blob", status="ok"))
        else:
            services.append(
                ServiceStatus(
                    name="blob",
                    status="error",
                    detail="Azure Blob unreachable",
                )
            )

    overall_status = "ok"
    if any(s.status == "error" for s in services):
        overall_status = "error"
    elif any(s.status == "degraded" for s in services):
        overall_status = "degraded"

    return HealthResponse(status=overall_status, version=API_VERSION, services=services)


async def _find_existing_by_fingerprint(digest: str):
    try:
        db = get_db()
        doc = db.document_memory.find_one(
            {"layer0.contentfingerprint": digest},
            {"layer0.documentid": 1},
        )
        if doc:
            layer0 = doc.get("layer0") or {}
            documentid = layer0.get("documentid")
            if documentid:
                return await mongo_store.get(documentid)
    except Exception:
        pass
    return None


def _detect_media_type(file: UploadFile, media_type: Optional[MediaType]) -> MediaType:
    if media_type:
        return media_type

    ctype = file.content_type or ""
    if ctype.startswith("image/"):
        return MediaType.imagem
    if ctype.startswith("video/"):
        return MediaType.video
    if ctype.startswith("audio/"):
        return MediaType.audio
    return MediaType.documento


def _append_processing_event(
    dm: DocumentMemory,
    *,
    etapa: str,
    engine: str,
    status: str = "success",
    detalhes: Optional[dict] = None,
) -> None:
    append_processing_event(
        dm,
        etapa=etapa,
        engine=engine,
        status=status,
        detalhes=detalhes,
    )


def _drop_none(value):
    return sanitize_processing_details(value)


def _env_flag(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"})


def _blob_metadata_from_dm(dm: DocumentMemory) -> Optional[dict]:
    if dm.layer1 is None or not dm.layer1.artefatos:
        return None
    metadata = dm.layer1.artefatos[0].metadados_nativos or {}
    blob_data = metadata.get("blob_storage")
    return blob_data if isinstance(blob_data, dict) else None


def _maybe_upload_original_to_blob(local_path: Path, artefact_id: str) -> Optional[dict]:
    if not _env_flag("RELLUNA_ENABLE_REMOTE_BLOB_INGEST", "0"):
        return None

    backend = AzureBlobBackend()
    if not backend.is_configured:
        return None

    store = AzureBlobArtefactStore()
    blob_path = store.upload(local_path, artefact_id)
    return {
        "container": store.container_name,
        "blob_path": blob_path,
        "blob_uri": store.blob_url_for(artefact_id),
        "uploaded_at": utcnow().isoformat(),
    }


def _ocr_error_message(exc: Exception) -> str:
    raw_message = str(exc).strip() or exc.__class__.__name__
    if "tesseract process timeout" in raw_message.lower():
        return (
            "OCR excedeu o timeout operacional no PDF escaneado. "
            "A extração foi interrompida de forma controlada; tente reduzir resolução/páginas "
            "ou executar OCR assíncrono."
        )
    return raw_message


def _stage_error_details(exc: Exception) -> dict:
    details = {
        "error_type": exc.__class__.__name__,
        "message": _ocr_error_message(exc),
        "traceback_tail": traceback.format_exc(limit=8),
    }
    raw_message = str(exc).strip()
    if raw_message and raw_message != details["message"]:
        details["cause_message"] = raw_message
    if "tesseract process timeout" in raw_message.lower():
        details["code"] = "ocr_timeout"
        details["warning_code"] = "ocr_timeout"
        details["severity"] = "error"
    return details


def _collect_stage_warnings(dm: DocumentMemory, stage: str) -> List[dict]:
    if stage != "decompose_pdf_into_subdocuments" or dm.layer2 is None:
        return []

    sig = dm.layer2.sinais_documentais.get("ocr_warnings_v1")
    if not sig or not getattr(sig, "valor", None):
        return []

    try:
        warnings = json.loads(sig.valor)
    except Exception:
        return []

    if not isinstance(warnings, list):
        return []
    return [warning for warning in warnings if isinstance(warning, dict)]


def _record_stage_error(
    dm: DocumentMemory,
    stage: str,
    exc: Exception,
    engine: str,
    *,
    duration_ms: Optional[float] = None,
) -> None:
    _append_processing_event(
        dm,
        etapa=stage,
        engine=engine,
        status="error",
        detalhes={**_stage_error_details(exc), "duration_ms": duration_ms},
    )


def _http_stage_error(documentid: str, pipeline: str, stage: str, exc: Exception) -> HTTPException:
    details = _stage_error_details(exc)
    return HTTPException(
        status_code=500,
        detail={
            "documentid": documentid,
            "pipeline": pipeline,
            "stage": stage,
            "error_type": details["error_type"],
            "message": details["message"],
            **{key: value for key, value in details.items() if key in {"code", "severity", "cause_message"}},
        },
    )


async def _run_stage(dm: DocumentMemory, stage: str, engine: str, fn: Callable[[], Awaitable[DocumentMemory] | DocumentMemory]) -> DocumentMemory:
    started = perf_counter()
    try:
        result = fn()
        if hasattr(result, "__await__"):
            dm = await result
        else:
            dm = result
        duration = elapsed_ms(started)
        _append_processing_event(
            dm,
            etapa=stage,
            engine=engine,
            detalhes={"duration_ms": duration},
        )
        for warning in _collect_stage_warnings(dm, stage):
            _append_processing_event(
                dm,
                etapa=stage,
                engine=engine,
                status="warning",
                detalhes={**warning, "duration_ms": duration},
            )
        return dm
    except Exception as exc:
        _record_stage_error(dm, stage, exc, engine, duration_ms=elapsed_ms(started))
        raise


def _collect_preflight_signals(dm: DocumentMemory) -> PreflightSignals:
    return collect_preflight_signals(dm)


def _decide_processing_mode(sig: PreflightSignals) -> ProcessingDecision:
    return decide_processing_mode(sig)


def _should_run_transcription(dm: DocumentMemory) -> bool:
    if dm.layer1 is None:
        return False
    return dm.layer1.midia in {MediaType.audio, MediaType.video}


def _needs_escalation_after_extract(dm: DocumentMemory) -> bool:
    return needs_escalation_after_extract(dm)


async def _run_fast_pipeline(dm: DocumentMemory) -> DocumentMemory:
    dm = await _run_stage(dm, "extract_basic", "deterministic_extractors.basic", lambda: extract_basic(dm))
    dm = await _run_stage(dm, "apply_page_analysis", "services.page_extraction.page_pipeline", lambda: apply_page_analysis(dm))
    dm = await _run_stage(dm, "apply_legal_extraction", "services.legal.legal_pipeline", lambda: apply_legal_extraction(dm))
    dm = await _run_stage(dm, "apply_entities_canonical_v1", "services.entities.entities_canonical_v1", lambda: apply_entities_canonical_v1(dm))

    if dm.layer0:
        dm.layer0.juridicalreadinesslevel = max(dm.layer0.juridicalreadinesslevel or 0, 1)

    return dm


async def _run_standard_pipeline(dm: DocumentMemory) -> DocumentMemory:
    dm = await _run_stage(dm, "extract_basic", "deterministic_extractors.basic", lambda: extract_basic(dm))
    dm = await _run_stage(dm, "decompose_pdf_into_subdocuments", "services.pdf_decomposition.decompose_pdf_v1", lambda: decompose_pdf_into_subdocuments(dm))
    dm = await _run_stage(dm, "apply_page_analysis", "services.page_extraction.page_pipeline", lambda: apply_page_analysis(dm))
    dm = await _run_stage(dm, "apply_legal_extraction", "services.legal.legal_pipeline", lambda: apply_legal_extraction(dm))
    dm = await _run_stage(dm, "apply_entities_canonical_v1", "services.entities.entities_canonical_v1", lambda: apply_entities_canonical_v1(dm))

    if _should_run_transcription(dm):
        dm = await _run_stage(dm, "apply_transcription_contextual", "services.transcription.asr", lambda: apply_transcription_to_layer2(dm))

    if dm.layer0:
        dm.layer0.juridicalreadinesslevel = max(dm.layer0.juridicalreadinesslevel or 0, 1)

    return dm


async def _run_forensic_pipeline(dm: DocumentMemory) -> DocumentMemory:
    dm = await _run_stage(dm, "extract_basic", "deterministic_extractors.basic", lambda: extract_basic(dm))
    dm = await _run_stage(dm, "decompose_pdf_into_subdocuments", "services.pdf_decomposition.decompose_pdf_v1", lambda: decompose_pdf_into_subdocuments(dm))
    dm = await _run_stage(dm, "apply_page_analysis", "services.page_extraction.page_pipeline", lambda: apply_page_analysis(dm))
    dm = await _run_stage(dm, "apply_legal_extraction", "services.legal.legal_pipeline", lambda: apply_legal_extraction(dm))
    dm = await _run_stage(dm, "apply_entities_canonical_v1", "services.entities.entities_canonical_v1", lambda: apply_entities_canonical_v1(dm))

    if _should_run_transcription(dm):
        dm = await _run_stage(dm, "apply_transcription_contextual", "services.transcription.asr", lambda: apply_transcription_to_layer2(dm))

    if dm.layer0:
        dm.layer0.juridicalreadinesslevel = max(dm.layer0.juridicalreadinesslevel or 0, 1)

    return dm


async def _run_extract_pipeline(dm: DocumentMemory) -> DocumentMemory:
    if not USE_ADAPTIVE_PIPELINE:
        return await _run_standard_pipeline(dm)

    preflight = _collect_preflight_signals(dm)
    decision = _decide_processing_mode(preflight)

    _append_processing_event(
        dm,
        etapa="processing_decision",
        engine="services.orchestration.decision_v1",
        detalhes=build_processing_decision_details(preflight, decision),
    )

    if decision.mode == "fast":
        dm = await _run_fast_pipeline(dm)

        if _needs_escalation_after_extract(dm):
            _append_processing_event(
                dm,
                etapa="processing_escalation",
                engine="services.orchestration.decision_v1",
                status="warning",
                detalhes=build_escalation_details(from_mode="fast", to_mode="standard"),
            )
            dm = await _run_standard_pipeline(dm)

        return dm

    if decision.mode == "forensic":
        return await _run_forensic_pipeline(dm)

    return await _run_standard_pipeline(dm)


async def _run_infer_pipeline(dm: DocumentMemory) -> DocumentMemory:
    if dm.layer2 is None:
        raise HTTPException(status_code=400, detail="Execute /extract antes de /infer_context")

    dm = await _run_stage(dm, "timeline_seed_v2", "deterministic_extractors.timeline_seed_v2", lambda: seed_timeline_v2(dm))
    dm = await _run_stage(dm, "infer_layer3", "taxonomy_rules", lambda: infer_layer3(dm))
    dm = await _run_stage(dm, "apply_layer4", "normalization", lambda: apply_layer4(dm))
    if dm.layer4 is None:
        dm.layer4 = Layer4SemanticNormalization()
    dm = await _run_stage(dm, "apply_layer5", "services.derivatives.layer5", lambda: apply_layer5(dm))
    await _run_stage(dm, "persist_read_model", "services.read_model.projector", lambda: persist_document_read_model(dm))

    if dm.layer0:
        has_timeline = dm.layer2 is not None and "timeline_seed_v2" in dm.layer2.sinais_documentais
        dm.layer0.juridicalreadinesslevel = max(dm.layer0.juridicalreadinesslevel or 0, 3 if has_timeline else 2)

    return dm


@app.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    media_type: Optional[MediaType] = Form(None),
    origin: Optional[OriginType] = Form(None),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Arquivo sem nome")

    if file.filename.lower().endswith(".heic"):
        raise HTTPException(status_code=415, detail="HEIC requires normalization")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    digest = sha256(content).hexdigest()

    existing = await _find_existing_by_fingerprint(digest)
    if existing is not None:
        existing_dm = DocumentMemory.model_validate(existing) if isinstance(existing, dict) else existing
        existing_uri = None
        blob_metadata = _blob_metadata_from_dm(existing_dm)
        if existing_dm.layer1 and existing_dm.layer1.artefatos:
            existing_uri = existing_dm.layer1.artefatos[0].uri
        return {
            "documentid": existing_dm.layer0.documentid,
            "blob_uri": (blob_metadata or {}).get("blob_uri"),
            "artifact_uri": existing_uri,
            "local_file_uri": existing_uri,
            "storage_kind": ("azure_blob+local_file" if blob_metadata else _LOCAL_FILE_STORAGE_KIND),
            "storage_state": ("blob_and_local_file_persisted" if blob_metadata else _LOCAL_FILE_STORAGE_STATE),
            "is_remote_blob": bool(blob_metadata),
            "hash": digest,
            "deduplicated": True,
        }

    filename = f"{digest}_{file.filename}"
    target_path = UPLOAD_DIR / filename
    target_path.write_bytes(content)

    midia = _detect_media_type(file, media_type)
    origem = origin or OriginType.digital_nativo
    documentid = str(uuid4())

    layer0 = Layer0(
        documentid=documentid,
        contentfingerprint=digest,
        fingerprint_algorithm="sha256",
        ingestiontimestamp=utcnow(),
        ingestionagent="api",
        original_filename=file.filename,
        mimetype=file.content_type,
        size_bytes=len(content),
        authenticitystate="preservado_com_hash_local",
        integrityproofs=[IntegrityProof.local_sha256(digest)],
        juridicalreadinesslevel=0,
        custodychain=[
            CustodyEvent(
                etapa="ingest",
                agente="api",
                acao="store_original",
                origem_uri=None,
                destino_uri=str(target_path),
                detalhes={
                    "filename": file.filename,
                    "mimetype": file.content_type,
                    "size_bytes": len(content),
                },
            )
        ],
        processingevents=[
            ProcessingEvent(
                etapa="ingest",
                engine="api",
                status="success",
                detalhes={
                    "media_type_detected": midia.value,
                    "origin_type": origem.value,
                },
            )
        ],
    )

    layer1 = Layer1(
        midia=midia,
        origem=origem,
        artefatos=[
            ArtefatoBruto(
                id=documentid,
                tipo=ArtefatoTipo.original,
                uri=str(target_path),
                nome=file.filename,
                mimetype=file.content_type,
                tamanho_bytes=len(content),
                hash_sha256=digest,
            )
        ],
    )

    dm = DocumentMemory(version=DOCUMENT_MEMORY_VERSION, layer0=layer0, layer1=layer1)

    blob_metadata = None
    try:
        blob_metadata = _maybe_upload_original_to_blob(target_path, documentid)
    except Exception as exc:
        dm.layer0.processingevents.append(
            ProcessingEvent(
                etapa="blob_upload",
                engine="infra.blob.azure",
                status="warning",
                detalhes={"message": str(exc)},
            )
        )

    if blob_metadata:
        artefact = dm.layer1.artefatos[0]
        artefact.metadados_nativos = artefact.metadados_nativos or {}
        artefact.metadados_nativos["blob_storage"] = blob_metadata
        dm.layer0.custodychain.append(
            CustodyEvent(
                etapa="ingest",
                agente="api",
                acao="copy",
                origem_uri=str(target_path),
                destino_uri=blob_metadata["blob_uri"],
                detalhes={
                    "container": blob_metadata["container"],
                    "blob_path": blob_metadata["blob_path"],
                },
            )
        )
        dm.layer0.processingevents.append(
            ProcessingEvent(
                etapa="blob_upload",
                engine="infra.blob.azure",
                status="success",
                detalhes={
                    "container": blob_metadata["container"],
                    "blob_path": blob_metadata["blob_path"],
                },
            )
        )

    if midia == MediaType.imagem:
        try:
            nsfw_result = check_image_nsfw(target_path, threshold=0.7)
            if nsfw_result:
                layer1.artefatos[0].metadados_nativos = layer1.artefatos[0].metadados_nativos or {}
                layer1.artefatos[0].metadados_nativos["nsfw"] = nsfw_result.to_dict()
        except Exception:
            pass

    await mongo_store.save(dm)

    return {
        "documentid": layer0.documentid,
        "blob_uri": (blob_metadata or {}).get("blob_uri"),
        "artifact_uri": str(target_path),
        "local_file_uri": str(target_path),
        "storage_kind": ("azure_blob+local_file" if blob_metadata else _LOCAL_FILE_STORAGE_KIND),
        "storage_state": ("blob_and_local_file_persisted" if blob_metadata else _LOCAL_FILE_STORAGE_STATE),
        "is_remote_blob": bool(blob_metadata),
        "hash": digest,
        "deduplicated": False,
    }


@app.post("/process")
async def process_document(
    file: UploadFile = File(...),
    media_type: Optional[MediaType] = Form(None),
    origin: Optional[OriginType] = Form(None),
):
    ingest_result = await ingest(file=file, media_type=media_type, origin=origin)
    documentid = ingest_result["documentid"]

    dm_dict = await mongo_store.get(documentid)
    if dm_dict is None:
        raise HTTPException(status_code=500, detail="Documento não encontrado após ingest")

    dm = DocumentMemory.model_validate(dm_dict)
    try:
        dm = await _run_extract_pipeline(dm)
        dm = await _run_infer_pipeline(dm)
        await mongo_store.save(dm)
    except HTTPException:
        raise
    except Exception as exc:
        _record_stage_error(dm, "process_document", exc, "api.process")
        await mongo_store.save(dm)
        raise _http_stage_error(documentid, "process", "process_document", exc)

    return {
        "documentid": documentid,
        "hash": ingest_result["hash"],
        "deduplicated": ingest_result.get("deduplicated", False),
        "document": to_contract(dm),
    }


@app.post("/extract/{documentid}")
async def extract(documentid: str):
    dm_dict = await mongo_store.get(documentid)
    if dm_dict is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    dm = DocumentMemory.model_validate(dm_dict)
    try:
        dm = await _run_extract_pipeline(dm)
        await mongo_store.save(dm)
        return to_contract(dm)
    except HTTPException:
        raise
    except Exception as exc:
        await mongo_store.save(dm)
        failed_stage = (dm.layer0.processingevents[-1].etapa if dm.layer0 and dm.layer0.processingevents else "extract")
        raise _http_stage_error(documentid, "extract", failed_stage, exc)


@app.post("/infer_context/{documentid}")
async def infer_context(documentid: str):
    dm_dict = await mongo_store.get(documentid)
    if dm_dict is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    dm = DocumentMemory.model_validate(dm_dict)
    try:
        dm = await _run_infer_pipeline(dm)
        await mongo_store.save(dm)
        return to_contract(dm)
    except HTTPException:
        raise
    except Exception as exc:
        await mongo_store.save(dm)
        failed_stage = (dm.layer0.processingevents[-1].etapa if dm.layer0 and dm.layer0.processingevents else "infer_context")
        raise _http_stage_error(documentid, "infer_context", failed_stage, exc)


@app.get("/documents/{documentid}")
async def get_document(documentid: str):
    dm = await mongo_store.get(documentid)
    if dm is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    if isinstance(dm, dict):
        return dm

    return dm.model_dump(mode="json", exclude_none=False)


@app.get("/documents/{document_id}/narrative")
async def get_document_narrative(document_id: str):
    dm_dict = await mongo_store.get(document_id)
    if dm_dict is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    dm = DocumentMemory.model_validate(dm_dict)
    narrative = generate_factual_narrative(dm)
    return {"documentid": document_id, "narrative": narrative}


@app.get("/documents/{documentid}/timeline")
async def get_document_timeline(documentid: str):
    dm_dict = await mongo_store.get(documentid)
    if dm_dict is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    dm = DocumentMemory.model_validate(dm_dict)
    return build_document_timeline_read_model(dm)


@app.get("/documents/{documentid}/case")
async def get_document_case(documentid: str):
    dm_dict = await mongo_store.get(documentid)
    if dm_dict is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado")

    dm = DocumentMemory.model_validate(dm_dict)
    return build_document_case_read_model(dm)
