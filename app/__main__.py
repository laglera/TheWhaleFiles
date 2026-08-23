"""Arranque local y en contenedor.

En el portátil se escucha sólo en la interfaz local, que es lo que se quiere.
Dentro de un contenedor eso deja la aplicación inalcanzable desde fuera: hay
que atender en todas las interfaces y en el puerto que asigne el proveedor,
que Railway y compañía entregan en la variable PORT.
"""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
