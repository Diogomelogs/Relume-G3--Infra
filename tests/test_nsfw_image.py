from pathlib import Path

import pytest

from relluna.services.content_safety.nsfw import analyze_image_for_nsfw


def test_analyze_image_for_nsfw_returns_safe_for_golden_image():
    # Usa uma imagem golden já existente no repo
    img_path = Path("tests/data/golden/IMG_0249.JPG")
    if not img_path.exists():
        pytest.skip("golden image fixture ausente no checkout atual")

    result = analyze_image_for_nsfw(img_path)

    # Implementação mínima: não bloqueia nada
    assert result.block is False
    assert result.label in {"safe", "unknown"}
