from pathlib import Path
from datetime import datetime

import pytest

from relluna.core.document_memory import (
    DocumentMemory,
    Layer0Custodia,
    Layer1Artefatos,
    ArtefatoBruto,
    MediaType,
    OriginType,
    ConfidenceState,
)
from relluna.services.deterministic_extractors import basic


def _build_minimal_video_dm(video_path: Path) -> DocumentMemory:
    layer0 = Layer0Custodia(
        documentid="test-video-docid",
        contentfingerprint="dummy-hash-video",
        ingestiontimestamp=datetime.utcnow(),
        ingestionagent="test_ingest_video",
    )

    artefato = ArtefatoBruto(
        id=video_path.name,
        tipo="original",
        uri=str(video_path),
        metadados_nativos={},
    )

    layer1 = Layer1Artefatos(
        midia=MediaType.video,
        origem=OriginType.digital_nativo,
        artefatos=[artefato],
    )

    return DocumentMemory(
        layer0=layer0,
        layer1=layer1,
    )


def test_extract_basic_video_uses_helper(monkeypatch, tmp_path: Path):
    # 1) Cria um arquivo "de mentira" de vídeo
    video_path = tmp_path / "teste.mp4"
    video_path.write_bytes(b"dummy-video-content")
    assert video_path.exists()

    # 2) Garante que o helper é chamado e retorna uma duração estável
    def fake_video_duration(path: Path) -> float:
        assert path == video_path
        return 1.23

    monkeypatch.setattr(basic, "_video_duration_seconds", fake_video_duration)

    # 3) Constrói DM mínimo
    dm = _build_minimal_video_dm(video_path)

    # 4) Roda o extrator
    dm_out = basic.extract_basic(dm)
    layer2 = dm_out.layer2
    assert layer2 is not None

    # 5) Verifica que duracao_segundos veio do helper, confirmado
    assert layer2.duracao_segundos is not None
    assert abs(layer2.duracao_segundos.valor - 1.23) < 1e-6
    assert layer2.duracao_segundos.estado == ConfidenceState.confirmado
