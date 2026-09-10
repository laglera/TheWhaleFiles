"""Lo que responde la aplicación entera por ASGI, sin TestClient: HEAD, rutas
con parámetros inválidos y errores con la página de la casa."""

import asyncio
import unittest


def call(method, path, query=b""):
    """Una petición completa contra la aplicación ASGI; devuelve (estado, cuerpo)."""
    from app.main import app

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("203.0.113.7", 5000),
        "root_path": "",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query,
        "headers": [(b"host", b"testserver")],
    }
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    start = next(message for message in sent if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
    return start["status"], dict(start["headers"]), body


class HeadTests(unittest.TestCase):
    def test_head_answers_like_get_without_a_body(self):
        # Los monitores de disponibilidad preguntan con HEAD, y recibían 405.
        status, headers, body = call("HEAD", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertIn(b"content-length", headers)

    def test_get_still_has_its_body(self):
        status, _headers, body = call("GET", "/health")
        self.assertEqual(status, 200)
        self.assertIn(b"TheWhaleFiles", body)


class InvalidParameterTests(unittest.TestCase):
    def test_a_profile_with_a_non_numeric_id_is_a_404_page(self):
        # Antes enseñaba el JSON del validador de FastAPI.
        status, headers, body = call("GET", "/politicians/abc")
        self.assertEqual(status, 404)
        self.assertIn(b"text/html", headers[b"content-type"])

    def test_the_api_keeps_its_validation_error(self):
        status, headers, body = call("GET", "/api/trades", b"limit=0")
        self.assertEqual(status, 422)
        self.assertIn(b"application/json", headers[b"content-type"])


if __name__ == "__main__":
    unittest.main()
