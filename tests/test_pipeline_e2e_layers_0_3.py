# tests/test_pipeline_e2e_layers_0_3.py

from pathlib import Path
import copy
import json

import pytest
from fastapi.testclient import TestClient

from relluna.core.document_memory import MediaType
from relluna.services.ingestion.api import app  # ajuste se o app estiver noutro módulo


BASE_DIR = Path(__file__).resolve().parent
GOLDEN_DIR = BASE_DIR / "data" / "golden"
MEDIA_DIR = BASE_DIR / "data" / "media"


@pytest.fixture(scope="module")
def client():
    # Usa o padrão with se você já estiver usando isso nos outros testes; aqui simplificado.
    with TestClient(app) as c:
        yield c


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_dm_for_comparison(dm: dict) -> dict:
    """
    Remove/normaliza campos altamente dinâmicos (timestamps, IDs de eventos),
    mantendo a estrutura e os valores estáveis (hash, estados, métricas, etc.).
    """
    dm = copy.deepcopy(dm)

    # Layer0: zera só o que é puramente temporal ou de grafo de versão
    layer0 = dm.get("layer0", {})
    if "ingestiontimestamp" in layer0:
        layer0["ingestiontimestamp"] = ""

    for ev in layer0.get("processingevents", []):
        if "timestamp" in ev:
            ev["timestamp"] = ""
        if "id" in ev:
            ev["id"] = ""  # se você gerar IDs aleatórios

    for vg in layer0.get("versiongraph", []):
        if "createdat" in vg:
            vg["createdat"] = ""

    for proof in layer0.get("integrityproofs", []):
        if "emitidoem" in proof:
            proof["emitidoem"] = ""

    # Layer1: createdat de artefatos pode variar levemente; normaliza.
    layer1 = dm.get("layer1", {})
    for art in layer1.get("artefatos", []):
        if "createdat" in art:
            art["createdat"] = ""

    # Se você tiver qualquer outro campo de timestamp em layers 2/3, trate aqui.
    # Ex.: nada na spec atual exige, então podemos deixar como está.
    return dm


# Casos E2E: (arquivo bruto, golden DM correspondente, content-type)
E2E_CASES = [
    pytest.param(
        "image_exif.jpg",
        "dm_image_exif_complete.json",
        "image/jpeg",
        id="e2e_image_exif",
    ),
    pytest.param(
        "image_analog.jpg",
        "dm_image_analog_no_exif.json",
        "image/jpeg",
        id="e2e_image_analog",
    ),
    pytest.param(
        "simple.pdf",
        "dm_pdf_simple.json",
        "application/pdf",
        id="e2e_pdf_simple",
    ),
    pytest.param(
        "audio.wav",
        "dm_audio_wav.json",
        "audio/wav",
        id="e2e_audio_wav",
    ),
]


@pytest.mark.parametrize("media_filename, golden_filename, content_type", E2E_CASES)
def test_pipeline_e2e_matches_golden_dm(client, media_filename, golden_filename, content_type):
    media_path = MEDIA_DIR / media_filename
    golden_dm = load_json(GOLDEN_DIR / golden_filename)

    # 1) /ingest
    with media_path.open("rb") as f:
        resp = client.post(
            "/ingest",
            files={"file": (media_filename, f, content_type)},
        )
    assert resp.status_code == 200
    data = resp.json()
    documentid = data["documentid"]
    assert documentid  # sanity

    # 2) /extract/{id} - CAMADA 2
    resp = client.post(f"/extract/{documentid}")
    assert resp.status_code == 200
    dm_after_extract = resp.json()
    # Layer2 deve existir após extract
    assert dm_after_extract["layer2"] is not None

    # 3) /infer_context/{id} - CAMADA 3
    resp = client.post(f"/infer_context/{documentid}")
    assert resp.status_code == 200
    dm_after_infer = resp.json()
    # Layer3 pode ser parcial, mas o objeto deve existir (nem que seja com todos campos null).
    assert "layer3" in dm_after_infer

    # 4) GET /documents/{id} - DM final
    resp = client.get(f"/documents/{documentid}")
    assert resp.status_code == 200
    live_dm = resp.json()

    # 5) Normaliza para comparação “flexível”
    norm_live = normalize_dm_for_comparison(live_dm)
    norm_golden = normalize_dm_for_comparison(golden_dm)

    # 6) Asserções de igualdade estrutural
    # Você pode começar com igualdade completa e relaxar se algum campo realmente precisar ser dinâmico.
    assert norm_live["version"] == norm_golden["version"]
    assert norm_live["layer0"]["documentid"]  # IDs podem diferir, então não compara valor exato aqui.
    assert norm_live["layer1"]["midia"] == norm_golden["layer1"]["midia"]
    assert norm_live["layer1"]["origem"] == norm_golden["layer1"]["origem"]

    # Campos de Layer2 devem bater segundo o contrato por tipo de mídia.
    midia = norm_live["layer1"]["midia"]
    assert_layer2_matches_for_media(midia, norm_live.get("layer2"), norm_golden.get("layer2"))

    # Contrato mínimo de Layer3 por mídia (evita travar evolução de inferência).
    assert_layer3_matches_for_media(midia, norm_live.get("layer3"), norm_golden.get("layer3"))


def _pick(d: dict, keys: list[str]) -> dict:
    return {k: d.get(k) for k in keys}


def assert_layer2_matches_for_media(midia: str, l2_live: dict, l2_golden: dict) -> None:
    """
    Compara apenas os campos de Layer2 que fazem parte do contrato E2E
    para cada tipo de mídia, em vez de exigir igualdade de todo o dict.
    """
    if midia == MediaType.imagem.value:
        # Imagem: dimensões, EXIF e qualidade de sinal
        keys = [
            "largura_px",
            "altura_px",
            "data_exif",
            "qualidade_sinal",
            "entidades_visuais_objetivas",
        ]
        assert _pick(l2_live, keys) == _pick(l2_golden, keys)

    elif midia == MediaType.documento.value:
        # PDF/documento: páginas e estado do OCR básico
        keys = [
            "largura_px",
            "altura_px",
            "num_paginas",
            "texto_ocr_literal",
            "entidades_visuais_objetivas",
        ]
        assert _pick(l2_live, keys) == _pick(l2_golden, keys)

    elif midia in (MediaType.audio.value, MediaType.video.value):
        # Áudio/vídeo: duração e entidades visuais objetivas (se existirem)
        keys = [
            "duracao_segundos",
            "entidades_visuais_objetivas",
        ]
        assert _pick(l2_live, keys) == _pick(l2_golden, keys)

    else:
        # Fallback: compara tudo (se aparecer alguma mídia nova sem contrato explícito)
        assert l2_live == l2_golden


def assert_layer3_matches_for_media(midia: str, l3_live: dict | None, l3_golden: dict | None) -> None:
    """
    Contrato mínimo de Layer3 por mídia para E2E.

    Detalhes de inferência (fonte, método, timestamp, campos extras)
    ficam a cargo dos testes específicos de contexto, não deste E2E.
    """
    if midia == MediaType.imagem.value:
        # Imagem: só garantimos que o tipo_evento é "imagem".
        assert l3_live is not None
        tipo = l3_live.get("tipo_evento")
        assert tipo is not None
        assert tipo.get("valor") == "imagem"

    elif midia == MediaType.documento.value:
        # Documento/PDF: por enquanto não travamos o pipeline no E2E por Layer3.
        # O comportamento detalhado de inferência de contexto é testado em testes dedicados.
        return

    else:
        # Para outras mídias, por ora não exigimos nada em Layer3 neste E2E.
        return
