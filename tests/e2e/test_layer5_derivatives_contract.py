from pathlib import Path
import json

from relluna.core.document_memory import DocumentMemory
from relluna.services.derivatives.layer5 import apply_layer5

BASE_DIR = Path(__file__).resolve().parents[1]
GOLDEN_DIR = BASE_DIR / "data" / "golden"


def _load_dm(name: str) -> DocumentMemory:
    raw = json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))
    return DocumentMemory.model_validate(raw)


def test_layer5_does_not_change_layers_0_to_4_for_image_exif():
    dm = _load_dm("dm_image_exif_complete.json")
    dm_before = dm.model_copy(deep=True)

    dm_after = apply_layer5(dm)

    # Layers 0–4 idênticos (ignorando completamente layer5)
    dump_after = dm_after.model_dump(exclude={"layer5"})
    dump_before = dm_before.model_dump(exclude={"layer5"})
    assert dump_after == dump_before

    # Layer5 presente no resultado
    assert dm_after.layer5 is not None
