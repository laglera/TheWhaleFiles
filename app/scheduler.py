from __future__ import annotations

import logging
import os
import threading

from app.sources import poll_official_sources

logger = logging.getLogger(__name__)

_polling_thread: threading.Thread | None = None
_polling_stop = threading.Event()

# Las fuentes republican el histórico entero en cada pasada, así que bajar de
# esto solo gasta ancho de banda: la latencia real la marca cuándo publica la
# fuente oficial, no cada cuánto preguntamos.
DEFAULT_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "900"))


def polling_enabled() -> bool:
    return os.getenv("ENABLE_POLLING", "1").lower() not in {"0", "false", "no"}


def start_polling_loop(interval_seconds: int | None = None) -> None:
    """Start a background polling loop for official disclosures."""
    global _polling_thread

    if _polling_thread is not None and _polling_thread.is_alive():
        return

    interval = interval_seconds or DEFAULT_INTERVAL_SECONDS

    def worker() -> None:
        while not _polling_stop.is_set():
            try:
                imported = poll_official_sources()
                if imported:
                    logger.info("Polling: %s operaciones nuevas importadas", len(imported))
            except Exception:
                # Un fallo de red no puede tumbar el hilo: se reintenta al ciclo
                # siguiente, pero queda registrado.
                logger.exception("Polling: fallo al consultar las fuentes oficiales")
            _polling_stop.wait(interval)

    _polling_stop.clear()
    _polling_thread = threading.Thread(target=worker, daemon=True)
    _polling_thread.start()


def stop_polling_loop() -> None:
    global _polling_thread
    _polling_stop.set()
    if _polling_thread is not None:
        _polling_thread.join(timeout=1.0)
        _polling_thread = None
