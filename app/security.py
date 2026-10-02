"""Defensas del perímetro: cabeceras y acceso de administración.

La web es de sólo lectura: no hay formularios ni sesiones que proteger. Quedan
dos cosas que sí importan en cuanto deja de vivir en localhost: que los
endpoints que escriben en la base o salen a la red no estén abiertos, y que el
navegador reciba las instrucciones mínimas sobre qué puede cargar.
"""

from __future__ import annotations

import os
import secrets
from typing import Optional

from fastapi import HTTPException, Request

# --- Acceso de administración ---------------------------------------------


def admin_token() -> Optional[str]:
    return os.getenv("ADMIN_TOKEN") or None


def require_admin(request: Request) -> None:
    """Puerta de los endpoints que escriben en la base o salen a la red.

    Sin ADMIN_TOKEN configurado no se abre de otra forma: responde 404, el mismo
    que una ruta inexistente, para no anunciar que existe una consola detrás.
    """
    expected = admin_token()
    submitted = request.headers.get("x-admin-token", "")
    if not expected or not secrets.compare_digest(expected, submitted):
        raise HTTPException(status_code=404, detail="Not found")


# --- Cabeceras -------------------------------------------------------------

# Hoja de estilos y tipografías se sirven desde el propio dominio: ya no se
# carga nada de Google Fonts, que recibía la IP de cada visitante. Los scripts,
# todos de la casa y en línea, se firman con un nonce por respuesta en vez de
# abrir 'unsafe-inline'. Los estilos sí lo necesitan: hay atributos style= en
# las plantillas para las barras de porcentaje.
def content_security_policy(nonce: str) -> str:
    return "; ".join(
        (
            "default-src 'self'",
            f"script-src 'self' 'nonce-{nonce}'",
            "style-src 'self' 'unsafe-inline'",
            "font-src 'self'",
            # Los retratos de Wikimedia se sirven desde su dominio.
            "img-src 'self' data: https:",
            "connect-src 'self'",
            "form-action 'self'",
            "base-uri 'self'",
            "frame-ancestors 'none'",
            "object-src 'none'",
        )
    )


# La documentación interactiva que genera FastAPI se pinta con Swagger UI
# servido desde un CDN. La política de la web lo bloquearía y la página se
# quedaría en blanco, así que esas tres rutas —y sólo esas— lo tienen permitido.
DOCS_PATHS = {"/docs", "/redoc", "/docs/oauth2-redirect"}
DOCS_CDN = "https://cdn.jsdelivr.net"


def docs_content_security_policy() -> str:
    return "; ".join(
        (
            "default-src 'self'",
            f"script-src 'self' 'unsafe-inline' {DOCS_CDN}",
            f"style-src 'self' 'unsafe-inline' {DOCS_CDN}",
            f"img-src 'self' data: {DOCS_CDN}",
            f"font-src 'self' {DOCS_CDN}",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "object-src 'none'",
        )
    )


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), interest-cohort=()",
}

HSTS = "max-age=31536000; includeSubDomains"


def is_https(request: Request) -> bool:
    """Si la petición llegó cifrada.

    HSTS sólo tiene sentido donde hay TLS: en local la web se sirve por http y
    el navegador la recordaría como https para siempre. Detrás de un proxy el
    cifrado termina antes de llegar aquí, así que el esquema del scope dice
    "http" aunque el visitante entrara por https; lo que lo delata es la
    cabecera que añade el propio proxy.
    """
    forwarded = request.headers.get("x-forwarded-proto", "")
    if forwarded:
        return forwarded.split(",")[0].strip() == "https"
    return request.url.scheme == "https"


async def security_headers_middleware(request: Request, call_next):
    # El nonce se genera antes de resolver la ruta: las plantillas lo reciben
    # por `request.state` y lo escriben en cada <script> de la página.
    nonce = secrets.token_urlsafe(16)
    request.state.csp_nonce = nonce

    response = await call_next(request)

    policy = (
        docs_content_security_policy()
        if request.url.path in DOCS_PATHS
        else content_security_policy(nonce)
    )
    response.headers.setdefault("Content-Security-Policy", policy)
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    if is_https(request):
        response.headers.setdefault("Strict-Transport-Security", HSTS)
    return response
