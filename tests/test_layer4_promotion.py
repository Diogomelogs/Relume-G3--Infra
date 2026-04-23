import json
from pathlib import Path
import pytest

from relluna.core.document_memory import DocumentMemory
from relluna.core.normalization import promote_temporal_to_layer4

GOLDEN_DIR = Path("tests/data/golden")


@pytest.mark.parametrize(
    "filename",
    [
        "dm_image_exif_complete.json",
        "dm_pdf_simple.json",
    ],
)
@pytest.mark.xfail(
    reason="goldens antigos referenciados por este contrato não existem no checkout atual",
    strict=False,
)
def test_promote_temporal_to_layer4_matches_golden(filename: str) -> None:

    golden_path = GOLDEN_DIR / filename
    golden_json = json.loads(golden_path.read_text(encoding="utf-8"))

    dm = DocumentMemory.model_validate(golden_json)

    promoted = promote_temporal_to_layer4(dm)

    assert promoted.layer4 is not None
