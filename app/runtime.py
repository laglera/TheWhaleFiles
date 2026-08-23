"""Dónde se está ejecutando la app.

En un servidor propio hay un proceso vivo, disco donde escribir y sitio para
un hilo de fondo. En una función serverless no hay nada de eso: se arranca por
petición, el disco es de sólo lectura y el proceso muere al responder. Varios
módulos necesitan saber en cuál de los dos mundos están.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

# Vercel define VERCEL=1 en build y en ejecución. Es la señal más fiable, y no
# depende de que nadie se acuerde de configurar una variable a mano.
SERVERLESS_MARKERS = ("VERCEL", "AWS_LAMBDA_FUNCTION_NAME")


def is_serverless() -> bool:
    return any(os.getenv(marker) for marker in SERVERLESS_MARKERS)


def utcnow() -> datetime:
    """Instante actual en UTC, sin zona horaria.

    `datetime.utcnow()` está deprecado desde Python 3.12, y su sustituto
    devuelve un datetime con zona. Las columnas DateTime de la base guardan
    fechas ingenuas, así que mezclar ambas hace reventar cualquier comparación:
    se pide con zona y se retira, que es justo lo que hacía la deprecada.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
