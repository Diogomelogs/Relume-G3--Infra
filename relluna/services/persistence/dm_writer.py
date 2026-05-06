from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone

from relluna.infra import mongo_store


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _storage_mode() -> str:
    try:
        coll = mongo_store.get_collection()
    except Exception:
        return "mongo_unavailable"
    if coll is None:
        return "in_memory"
    return "mongo"


def run_worker(*, once: bool = False, poll_interval_s: float = 5.0) -> int:
    """
    Worker mínimo funcional.

    Ainda não consome fila real, mas sobe como processo válido do projeto,
    verifica o backend configurado e emite heartbeat operacional explícito.
    """
    mode = _storage_mode()
    print(f"[{_utcnow()}] relluna-worker started mode={mode}", flush=True)

    if once:
        print(f"[{_utcnow()}] relluna-worker heartbeat mode={mode}", flush=True)
        return 0

    while True:
        print(f"[{_utcnow()}] relluna-worker heartbeat mode={mode}", flush=True)
        time.sleep(poll_interval_s)


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    once = "--once" in argv or os.getenv("RELLUNA_WORKER_ONCE", "0").strip() == "1"
    interval = float(os.getenv("RELLUNA_WORKER_POLL_INTERVAL_S", "5"))
    return run_worker(once=once, poll_interval_s=interval)


if __name__ == "__main__":
    raise SystemExit(main())
