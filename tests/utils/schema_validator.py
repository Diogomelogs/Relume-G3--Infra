import json
from pathlib import Path
from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema.json"

with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    _SCHEMA = json.load(f)

_validator = Draft202012Validator(_SCHEMA)


def validate_dm(dm_dict: dict):
    """
    Valida um Documento-Memória contra o schema.json.
    Lança AssertionError se inválido.
    """
    errors = sorted(_validator.iter_errors(dm_dict), key=lambda e: e.path)

    if errors:
        msgs = []
        for e in errors:
            path = ".".join(map(str, e.path))
            msgs.append(f"{path}: {e.message}")
        raise AssertionError(
            "Documento-Memória inválido segundo schema.json:\n"
            + "\n".join(msgs)
        )
