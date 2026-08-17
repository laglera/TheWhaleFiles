"""Punto de entrada para Vercel.

El runtime de Python de Vercel busca en este fichero una variable llamada
`app` y la sirve como aplicación ASGI. Todas las rutas del sitio se reescriben
hacia aquí desde vercel.json, así que este único fichero atiende la web entera.

En local no se usa: ahí sigue mandando `python -m app`, que levanta uvicorn.
"""

from app.main import app

__all__ = ["app"]
