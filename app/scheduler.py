from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta

from app.runtime import is_serverless, utcnow
from app.sources import poll_official_sources

logger = logging.getLogger(__name__)

_polling_thread: threading.Thread | None = None
_polling_stop = threading.Event()

# Las fuentes republican el histórico entero en cada pasada, así que bajar de
# esto solo gasta ancho de banda: la latencia real la marca cuándo publica la
# fuente oficial, no cada cuánto preguntamos.
DEFAULT_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "900"))

# La rentabilidad de copiar a cada persona se recalcula una vez al día: los
# cierres cambian una vez por sesión y el cálculo recorre a todo el mundo.
PERFORMANCE_EVERY = timedelta(hours=float(os.getenv("PERFORMANCE_EVERY_HOURS", "24")))
_last_performance: datetime | None = None


def refresh_analytics(now: datetime | None = None) -> bool:
    """Históricos de cotización y, una vez al día, la rentabilidad.

    Sin esto, fuera del refresco programado de producción nadie descargaba el
    histórico del SPY ni rellenaba la tabla `performance`, y la sección de
    rentabilidad no aparecía en ninguna ficha. El histórico va por tandas
    (HISTORY_MAX_SYMBOLS) y empieza siempre por el índice, así que la primera
    pasada ya deja algo con lo que comparar. Devuelve si recalculó.
    """
    global _last_performance

    from app.history import refresh_history
    from app.performance import compute_all

    now = now or utcnow()
    refresh_history(verbose=False)
    if _last_performance is not None and now - _last_performance < PERFORMANCE_EVERY:
        return False
    # Una vez al día también: nombre de empresa a los valores nuevos.
    try:
        from app.ticker_names import fill_ticker_names

        fill_ticker_names(verbose=False)
    except Exception:
        logger.exception("Polling: fallo al poner nombre a los valores")
    stats = compute_all(verbose=False)
    # Sin el índice descargado no se calcula nada: se reintenta en la pasada
    # siguiente en vez de esperar un día entero.
    if stats.get("people"):
        _last_performance = now
    return bool(stats.get("people"))


def polling_enabled() -> bool:
    # En serverless no hay proceso que sobreviva a la respuesta: el hilo se
    # cortaría a media pasada y sólo serviría para alargar cada petición.
    if is_serverless():
        return False
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
            # Las fichas ya no piden cotizaciones al abrirse: las deja listas
            # este hilo, que puede permitirse esperar al proveedor.
            try:
                from app.prices import warm_cache

                warm_cache(verbose=False)
            except Exception:
                logger.exception("Polling: fallo al refrescar las cotizaciones")
            try:
                refresh_analytics()
            except Exception:
                logger.exception("Polling: fallo al calcular históricos y rentabilidad")
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
