import json
from pathlib import Path

import pytest

# Se o __init__ já expõe o alias, usa assim:
from relluna.core.document_memory import DocumentMemory_v0_2_0
# Se não expuser, alternativa:
# from relluna.core.document_memory_v0_2_0 import DocumentMemory as DocumentMemory_v0_2_0


GOLDEN_DIR = Path(__file__).parent / "data" / "golden"

# Pega todos os GOLDEN v0.2.0
GOLDEN_V020 = sorted(GOLDEN_DIR.glob("GOLDEN — *.json"))


@pytest.mark.parametrize("path", GOLDEN_V020, ids=[p.name for p in GOLDEN_V020])
def test_goldens_v0_2_0_sao_validos(path: Path):
    """Cada JSON GOLDEN v0.2.0 deve ser validado pelo modelo DocumentMemory_v0_2_0."""
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    # Se der ValidationError aqui, o trace já mostra qual campo está incompatível.
    DocumentMemory_v0_2_0.model_validate(data)
