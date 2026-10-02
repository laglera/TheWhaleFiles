"""Pruebas de lo que protege el perímetro: puerta de administración y
cabeceras. Sin TestClient, como el resto del proyecto: las funciones se llaman
directamente."""

import os
import unittest

from fastapi import HTTPException
from starlette.requests import Request

from app import security


def make_request(path="/", headers=None, client=("203.0.113.7", 5000)):
    """Petición mínima, suficiente para lo que estas funciones consultan."""
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": ("testserver", 80),
            "path": path,
            "query_string": b"",
            "headers": raw_headers,
            "client": client,
        }
    )


class AdminGateTests(unittest.TestCase):
    def setUp(self):
        self.previous = os.environ.pop("ADMIN_TOKEN", None)

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("ADMIN_TOKEN", None)
        else:
            os.environ["ADMIN_TOKEN"] = self.previous

    def test_without_a_configured_token_the_door_does_not_exist(self):
        request = make_request(headers={"x-admin-token": "lo-que-sea"})
        with self.assertRaises(HTTPException) as raised:
            security.require_admin(request)
        # 404 y no 403: un 403 anunciaría que hay una consola detrás.
        self.assertEqual(raised.exception.status_code, 404)

    def test_a_wrong_token_is_rejected(self):
        os.environ["ADMIN_TOKEN"] = "el-bueno"
        request = make_request(headers={"x-admin-token": "el-malo"})
        with self.assertRaises(HTTPException) as raised:
            security.require_admin(request)
        self.assertEqual(raised.exception.status_code, 404)

    def test_a_missing_token_is_rejected(self):
        os.environ["ADMIN_TOKEN"] = "el-bueno"
        with self.assertRaises(HTTPException) as raised:
            security.require_admin(make_request())
        self.assertEqual(raised.exception.status_code, 404)

    def test_the_right_token_opens_it(self):
        os.environ["ADMIN_TOKEN"] = "el-bueno"
        request = make_request(headers={"x-admin-token": "el-bueno"})
        self.assertIsNone(security.require_admin(request))


class SecurityHeaderTests(unittest.IsolatedAsyncioTestCase):
    async def run_middleware(self, request):
        captured = {}

        async def call_next(passed):
            # El nonce se genera antes de resolver la ruta, que es cuando las
            # plantillas lo necesitan.
            captured["nonce"] = getattr(passed.state, "csp_nonce", None)
            from starlette.responses import PlainTextResponse

            return PlainTextResponse("ok")

        response = await security.security_headers_middleware(request, call_next)
        return response, captured["nonce"]

    async def test_the_nonce_reaches_the_route_and_the_policy(self):
        response, nonce = await self.run_middleware(make_request())
        self.assertTrue(nonce)
        self.assertIn(f"'nonce-{nonce}'", response.headers["content-security-policy"])

    async def test_the_usual_headers_travel(self):
        response, _ = await self.run_middleware(make_request())
        for header, value in security.SECURITY_HEADERS.items():
            self.assertEqual(response.headers[header], value)

    async def test_hsts_does_not_travel_over_plain_http(self):
        response, _ = await self.run_middleware(make_request())
        # En local la web se sirve por http y el navegador la recordaría como
        # https para siempre.
        self.assertNotIn("strict-transport-security", response.headers)

    async def test_hsts_travels_when_the_proxy_says_it_was_https(self):
        # Detrás de Vercel el cifrado termina en su proxy: el esquema del scope
        # dice "http" aunque el visitante entrara por https.
        request = make_request(headers={"x-forwarded-proto": "https"})
        response, _ = await self.run_middleware(request)
        self.assertEqual(response.headers["strict-transport-security"], security.HSTS)

    async def test_the_docs_page_may_load_its_cdn(self):
        # Swagger UI se sirve desde jsdelivr: con la política de la web, la
        # página de documentación se quedaría en blanco.
        response, _ = await self.run_middleware(make_request("/docs"))
        self.assertIn(security.DOCS_CDN, response.headers["content-security-policy"])

    async def test_the_rest_of_the_site_may_not(self):
        response, _ = await self.run_middleware(make_request("/"))
        self.assertNotIn(security.DOCS_CDN, response.headers["content-security-policy"])

    async def test_the_policy_forbids_being_framed(self):
        response, _ = await self.run_middleware(make_request())
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])


if __name__ == "__main__":
    unittest.main()


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        security.rate_limiter.reset()
        self.previous = os.environ.pop("RATE_LIMIT_API", None)

    def tearDown(self):
        security.rate_limiter.reset()
        if self.previous is None:
            os.environ.pop("RATE_LIMIT_API", None)
        else:
            os.environ["RATE_LIMIT_API"] = self.previous

    def test_the_window_lets_through_up_to_the_limit(self):
        limiter = security.RateLimiter()
        results = [limiter.hit("api", "1.2.3.4", 3, 60.0) for _ in range(4)]
        self.assertEqual(results[:3], [None, None, None])
        self.assertGreater(results[3], 0)

    def test_each_ip_has_its_own_count(self):
        limiter = security.RateLimiter()
        limiter.hit("api", "1.2.3.4", 1, 60.0)
        self.assertIsNone(limiter.hit("api", "5.6.7.8", 1, 60.0))

    def test_old_hits_fall_out_of_the_window(self):
        limiter = security.RateLimiter()
        self.assertIsNone(limiter.hit("api", "1.2.3.4", 1, 0.01))
        import time

        time.sleep(0.02)
        self.assertIsNone(limiter.hit("api", "1.2.3.4", 1, 0.01))

    def test_behind_the_proxy_the_real_ip_counts(self):
        request = make_request(headers={"x-forwarded-for": "198.51.100.9, 10.0.0.1"})
        self.assertEqual(security.client_ip(request), "198.51.100.9")
        request = make_request(headers={"x-real-ip": "198.51.100.10"})
        self.assertEqual(security.client_ip(request), "198.51.100.10")

    def test_pages_are_not_limited_only_the_api(self):
        self.assertIsNone(security.rate_limit_bucket("/"))
        self.assertIsNone(security.rate_limit_bucket("/politicians/3"))
        self.assertEqual(security.rate_limit_bucket("/api/trades"), "api")
        self.assertEqual(security.rate_limit_bucket("/api/poll-sources"), "admin")

    def test_the_api_answers_429_with_retry_after(self):
        from tests.test_http import call

        os.environ["RATE_LIMIT_API"] = "2"
        statuses = [call("GET", "/api/politicians")[0] for _ in range(3)]
        self.assertEqual(statuses, [200, 200, 429])
        _status, headers, _body = call("GET", "/api/politicians")
        self.assertIn(b"retry-after", headers)
        # Y lleva las cabeceras de seguridad como cualquier otra respuesta.
        self.assertIn(b"content-security-policy", headers)

    def test_the_admin_door_counts_before_checking_the_token(self):
        # Probar tokens a ciegas también gasta el cupo.
        from tests.test_http import call

        statuses = [call("POST", "/api/poll-sources")[0] for _ in range(6)]
        self.assertEqual(statuses[:5], [404] * 5)
        self.assertEqual(statuses[5], 429)
