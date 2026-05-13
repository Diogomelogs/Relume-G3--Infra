from datetime import datetime, UTC
from typing import Dict, Any

def now_utc():
    return datetime.now(UTC)

def make_processing_event(etapa: str, engine: str) -> Dict[str, Any]:
    return {
        "etapa": etapa,
        "engine": engine,
        "timestamp": now_utc().isoformat(),
    }