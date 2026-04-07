from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from relluna.core.document_memory import DocumentMemory
from relluna.core.document_memory.layer1 import MediaType
from relluna.core.document_memory.layer3 import ContextualTranscription, Layer3Evidence
from relluna.core.document_memory.transcription import TranscriptionSegment
from relluna.core.document_memory.types_basic import (
    ConfidenceState,
    EvidenceRef,
    InferenceMeta,
)

_SOURCE = "asr.whisper"
_METHOD = "whisper.transcribe"


@dataclass(frozen=True)
class ASROptions:
    enabled: bool = False
    language: Optional[str] = None
    model_name: str = "base"
    diarization: bool = False
    min_text_len: int = 1


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def get_asr_options_from_env() -> ASROptions:
    return ASROptions(
        enabled=True,
        language=os.getenv("RELLUNA_TRANSCRIPTION_LANGUAGE") or None,
        model_name=os.getenv("RELLUNA_TRANSCRIPTION_MODEL", "base"),
        diarization=_env_flag("RELLUNA_TRANSCRIPTION_DIARIZATION", "0"),
    )


def _ensure_ffmpeg_available() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
        return True
    except Exception:
        return False


def _extract_audio_from_video_to_wav(video_path: Path) -> Optional[Path]:
    if not _ensure_ffmpeg_available():
        return None

    tmp_dir = Path(tempfile.mkdtemp(prefix="relluna_asr_"))
    out_wav = tmp_dir / "audio.wav"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        str(out_wav),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        if out_wav.exists() and out_wav.stat().st_size > 0:
            return out_wav
        return None
    except Exception:
        return None


def _transcribe_with_whisper(audio_path: Path, opts: ASROptions) -> tuple[Optional[str], List[TranscriptionSegment], str]:
    try:
        import whisper  # type: ignore
    except Exception:
        return None, [], "missing_whisper"

    try:
        model = whisper.load_model(opts.model_name)
        kwargs = {}
        if opts.language:
            kwargs["language"] = opts.language

        result = model.transcribe(str(audio_path), **kwargs)

        text = (result.get("text") or "").strip()
        segments_out: List[TranscriptionSegment] = []

        for seg in result.get("segments") or []:
            seg_text = (seg.get("text") or "").strip()
            if not seg_text:
                continue
            segments_out.append(
                TranscriptionSegment(
                    start=float(seg.get("start", 0.0)),
                    end=float(seg.get("end", 0.0)),
                    text=seg_text,
                    speaker=None,
                )
            )

        if len(text) < opts.min_text_len:
            text = None

        return text, segments_out, f"whisper:{opts.model_name}"
    except Exception:
        return None, [], "whisper_error"


def _pick_primary_artifact_path(dm: DocumentMemory) -> Optional[Path]:
    try:
        arts = dm.layer1.artefatos or []
    except Exception:
        return None

    if not arts:
        return None

    original = None
    for a in arts:
        if getattr(a, "tipo", None) == "original":
            original = a
            break

    target = original or arts[0]
    uri = getattr(target, "uri", None)
    if not uri:
        return None

    return Path(uri)


def apply_transcription_to_layer2(dm: DocumentMemory, opts: Optional[ASROptions] = None) -> DocumentMemory:
    """
    Compatibilidade de nome.
    O pipeline novo não grava mais transcrição na Layer2.
    Grava em Layer3.transcricao_contextual.
    """
    opts = opts or get_asr_options_from_env()
    if not opts.enabled:
        return dm

    if not dm.layer1 or dm.layer1.midia not in {MediaType.audio, MediaType.video}:
        return dm

    media_path = _pick_primary_artifact_path(dm)
    if not media_path or not media_path.exists():
        return dm

    if dm.layer3 is None:
        dm.layer3 = Layer3Evidence()

    audio_path: Optional[Path]
    if dm.layer1.midia == MediaType.video:
        audio_path = _extract_audio_from_video_to_wav(media_path)
        if not audio_path:
            dm.layer3.transcricao_contextual = ContextualTranscription(
                engine=_SOURCE,
                metodo="ffmpeg_extract_failed",
                texto=None,
                segmentos=[],
                confianca=None,
                lastro=[],
                meta=InferenceMeta(engine=_SOURCE),
            )
            return dm
    else:
        audio_path = media_path

    text, segments, engine_label = _transcribe_with_whisper(audio_path, opts)

    lastro = [
        EvidenceRef(
            kind="artefato",
            uri=str(media_path),
            note="ASR contextual transcription",
            path="layer1.artefatos[0].uri",
        )
    ]

    dm.layer3.transcricao_contextual = ContextualTranscription(
        engine=_SOURCE,
        metodo=engine_label,
        texto=text,
        segmentos=segments,
        confianca=None,
        lastro=lastro,
        meta=InferenceMeta(engine=_SOURCE),
    )

    return dm