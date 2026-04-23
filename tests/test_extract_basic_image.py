# arquivo: tests/test_extract_basic_image.py

from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image

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


def _build_minimal_image_dm(image_path: Path) -> DocumentMemory:
    """
    Constrói um DocumentMemory mínimo de imagem (camadas 0 e 1)
    apontando o artefato original para image_path.
    """
    layer0 = Layer0Custodia(
        documentid="test-doc-uuid",
        contentfingerprint="5" * 64,
        ingestiontimestamp=datetime.now(timezone.utc),
        ingestionagent="test_ingest",
    )

    artefato = ArtefatoBruto(
        id=image_path.name,
        tipo="original",
        uri=str(image_path),  # o basic.py faz Path(art.uri)
        metadados_nativos={},
    )

    layer1 = Layer1Artefatos(
        midia=MediaType.imagem,
        origem=OriginType.digital_nativo,
        artefatos=[artefato],
    )

    return DocumentMemory(
        layer0=layer0,
        layer1=layer1,
    )


def test_extract_basic_image_populates_layer2(tmp_path: Path):
    # 1) Cria uma imagem simples em disco (sem EXIF)
    img_path = tmp_path / "imagem_teste.jpg"
    img = Image.new("RGB", (3264, 2448), color="white")
    img.save(img_path)

    assert img_path.exists()

    # 2) Constrói um DM mínimo apontando para essa imagem
    dm = _build_minimal_image_dm(img_path)

    # 3) Roda o extrator determinístico básico
    dm_out = extract_basic(dm)

    # 4) Verifica que layer2 foi preenchida
    assert dm_out.layer2 is not None
    layer2 = dm_out.layer2

    # largura/altura devem bater com a imagem
    assert layer2.largura_px is not None
    assert layer2.largura_px.valor == 3264.0
    assert layer2.largura_px.estado == ConfidenceState.confirmado

    assert layer2.altura_px is not None
    assert layer2.altura_px.valor == 2448.0
    assert layer2.altura_px.estado == ConfidenceState.confirmado

    # como a imagem criada não tem EXIF, data_exif deve existir
    # mas com valor=None e estado=insuficiente (sem crash)
    assert layer2.data_exif is not None
    assert layer2.data_exif.valor is None
    assert layer2.data_exif.estado == ConfidenceState.insuficiente

    # gps_exif não deve existir para essa imagem sem EXIF
    assert layer2.gps_exif is None

    # qualidade_sinal.resolucao deve estar preenchido com "3264x2448"
    assert layer2.qualidade_sinal is not None
    assert layer2.qualidade_sinal.resolucao is not None
    assert layer2.qualidade_sinal.resolucao.valor == "3264x2448"

    # foco (stub) deve ter algum valor numérico
    assert layer2.qualidade_sinal.foco is not None
    assert isinstance(layer2.qualidade_sinal.foco.valor, float)

    # entidades_visuais_objetivas ainda é lista vazia (placeholder)
    assert len(layer2.entidades_visuais_objetivas) >= 0
