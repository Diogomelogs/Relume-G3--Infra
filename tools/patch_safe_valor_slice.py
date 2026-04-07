from pathlib import Path
import re

ROOT = Path(".")
PATTERN = re.compile(
    r"(\.valor)\s*\[\s*:(\d+)\s*\]"
)

def patch_file(path: Path):
    text = path.read_text(encoding="utf-8")

    def replacer(match):
        # substitui (dm.layer2.texto_ocr_literal.valor or "")[:100] por (.valor or "")[:100]
        return f"{match.group(1)} or \"\")[:{match.group(2)}]"

    new_text = re.sub(
        r"\.valor\s*\[\s*:(\d+)\s*\]",
        lambda m: f"(dm.layer2.texto_ocr_literal.valor or \"\")[:{m.group(1)}]",
        text
    )

    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        print(f"Patched: {path}")

def main():
    for py in ROOT.rglob("*.py"):
        if "venv" in str(py) or "__pycache__" in str(py):
            continue
        patch_file(py)

if __name__ == "__main__":
    main()