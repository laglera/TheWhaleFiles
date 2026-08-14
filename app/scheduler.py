from __future__ import annotations

import threading
import time
from typing import Any

from app.sources import poll_official_sources

_polling_thread: threading.Thread | None = None
_polling_stop = threading.Event()


def start_polling_loop(interval_seconds: int = 300) -> None:
    """Start a background polling loop for official disclosures."""
    global _polling_thread

    if _polling_thread is not None and _polling_thread.is_alive():
        return

    def worker() -> None:
        while not _polling_stop.is_set():
            try:
                poll_official_sources()
            except Exception:
                pass
            _polling_stop.wait(interval_seconds)

    _polling_stop.clear()
    _polling_thread = threading.Thread(target=worker, daemon=True)
    _polling_thread.start()


def stop_polling_loop() -> None:
    global _polling_thread
    _polling_stop.set()
    if _polling_thread is not None:
        _polling_thread.join(timeout=1.0)
        _polling_thread = None
