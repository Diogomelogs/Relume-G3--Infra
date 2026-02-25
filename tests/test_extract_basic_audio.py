from pathlib import Path
from datetime import datetime
import wave
import struct

from relluna.core.document_memory import (
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    ArtefatoBruto,
    MediaType,
    OriginType,
    ConfidenceState,
)
from relluna.services.deterministic_extractors.basic import extract_basic


def _create_dummy_wav(path: Path, duration_sec: float = 1.0, sample_rate: int = 8000):
    """
    Cria um WAV mono silencioso com duração aproximada de duration_sec.
    """
    n_frames = int(duration_sec * sample_rate)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16 bits
        wf.setframerate(sample_rate)
        silence_frame = struct.pack("<h", 0)  # amostra zero
        wf.writeframes(silence_frame * n_frames)


def _build_minimal_audio_dm(wav_path: Path) -> DocumentMemory:
    layer0 = Layer0Custodia(
        documentid="test-audio-docid",
        contentfingerprint="dummy-hash-audio",
        ingestiontimestamp=datetime.utcnow(),
        ingestionagent="test_ingest_audio",
    )

    artefato = ArtefatoBruto(
        id=wav_path.name,
        tipo="original",
        uri=str(wav_path),
        metadados_nativos={},
    )

    layer1 = Layer1Artefatos(
        midia=MediaType.audio,
        origem=OriginType.digital_nativo,
        artefatos=[artefato],
    )

    return DocumentMemory(
        layer0=layer0,
        layer1=layer1,
    )


def test_extract_basic_audio_wav_duration(tmp_path: Path):
    # 1) Cria um WAV de ~1 segundo
    wav_path = tmp_path / "teste.wav"
    _create_dummy_wav(wav_path, duration_sec=1.0, sample_rate=8000)
    assert wav_path.exists()

    # 2) Constrói DM mínimo
    dm = _build_minimal_audio_dm(wav_path)

    # 3) Roda o extrator
    dm_out = extract_basic(dm)
    layer2 = dm_out.layer2
    assert layer2 is not None

    # 4) duracao_segundos deve estar preenchido e confirmado
    assert layer2.duracao_segundos is not None
    assert layer2.duracao_segundos.valor is not None
    # duração aproximada de 1s:
    assert abs(layer2.duracao_segundos.valor - 1.0) < 0.01
    assert layer2.duracao_segundos.estado == ConfidenceState.confirmado
