"""Dónde se está ejecutando la app.

En un servidor propio hay un proceso vivo, disco donde escribir y sitio para
un hilo de fondo. En una función serverless no hay nada de eso: se arranca por
petición, el disco es de sólo lectura y el proceso muere al responder. Varios
módulos necesitan saber en cuál de los dos mundos están.
"""

from __future__ import annotations

import os

# Vercel define VERCEL=1 en build y en ejecución. Es la señal más fiable, y no
# depende de que nadie se acuerde de configurar una variable a mano.
SERVERLESS_MARKERS = ("VERCEL", "AWS_LAMBDA_FUNCTION_NAME")


def is_serverless() -> bool:
    return any(os.getenv(marker) for marker in SERVERLESS_MARKERS)
