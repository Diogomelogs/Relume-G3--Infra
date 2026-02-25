from pathlib import Path

BASE = Path(__file__).parent

def main():
    (BASE / "relluna" / "services" / "ingestion").mkdir(parents=True, exist_ok=True)
    (BASE / "relluna" / "infra").mkdir(parents=True, exist_ok=True)

    for path in [
        BASE / "relluna" / "services" / "ingestion" / "__init__.py",
        BASE / "relluna" / "infra" / "__init__.py",
    ]:
        path.touch(exist_ok=True)

    api_path = BASE / "relluna" / "services" / "ingestion" / "api.py"
    if not api_path.exists():
        api_path.write_text(
            "from fastapi import FastAPI\n\n"
            "app = FastAPI()\n\n"
            "@app.get('/health')\n"
            "def health():\n"
            "    return {'status': 'ok'}\n"
        )

if __name__ == '__main__':
    main()
