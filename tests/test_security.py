"""Pruebas de lo que protege el perímetro: límite de intentos, puerta de
administración y cabeceras. Sin TestClient, como el resto del proyecto: las
funciones se llaman directamente y la base es una en memoria."""

import os
import unittest
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app import security
from app.models import Base, LoginAttempt
from app.runtime import utcnow


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


class ClientIpTests(unittest.TestCase):
    def test_uses_the_socket_address_when_there_is_no_proxy(self):
        self.assertEqual(security.client_ip(make_request()), "203.0.113.7")

    def test_prefers_the_first_address_of_x_forwarded_for(self):
        request = make_request(headers={"x-forwarded-for": "198.51.100.4, 10.0.0.1"})
        # Detrás de Vercel la conexión la abre su proxy: sin esto el límite se
        # aplicaría a todo el mundo a la vez.
        self.assertEqual(security.client_ip(request), "198.51.100.4")


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_a_fresh_address_has_its_whole_quota(self):
        self.assertFalse(security.attempts_exhausted(self.db, "login", "198.51.100.4"))

    def test_the_quota_runs_out(self):
        limit, _ = security.LIMITS["login"]
        for _ in range(limit):
            security.record_attempt(self.db, "login", "198.51.100.4")
        self.assertTrue(security.attempts_exhausted(self.db, "login", "198.51.100.4"))

    def test_the_quota_is_counted_per_address(self):
        limit, _ = security.LIMITS["login"]
        for _ in range(limit):
            security.record_attempt(self.db, "login", "198.51.100.4")
        self.assertFalse(security.attempts_exhausted(self.db, "login", "198.51.100.9"))

    def test_each_form_has_its_own_quota(self):
        limit, _ = security.LIMITS["login"]
        for _ in range(limit):
            security.record_attempt(self.db, "login", "198.51.100.4")
        self.assertFalse(security.attempts_exhausted(self.db, "signup", "198.51.100.4"))

    def test_getting_it_right_wipes_the_previous_failures(self):
        limit, _ = security.LIMITS["login"]
        for _ in range(limit):
            security.record_attempt(self.db, "login", "198.51.100.4")
        security.clear_attempts(self.db, "login", "198.51.100.4")
        self.assertFalse(security.attempts_exhausted(self.db, "login", "198.51.100.4"))

    def test_attempts_outside_the_window_do_not_count(self):
        limit, window = security.LIMITS["login"]
        old = utcnow() - window - timedelta(minutes=1)
        for _ in range(limit):
            self.db.add(LoginAttempt(scope="login", bucket="198.51.100.4", created_at=old))
        self.db.commit()
        self.assertFalse(security.attempts_exhausted(self.db, "login", "198.51.100.4"))

    def test_old_rows_are_swept_when_a_new_one_lands(self):
        # No hay proceso de limpieza en serverless: la tabla crecería sin fin.
        stale = utcnow() - security.PURGE_AFTER - timedelta(hours=1)
        self.db.add(LoginAttempt(scope="login", bucket="198.51.100.4", created_at=stale))
        self.db.commit()

        security.record_attempt(self.db, "login", "198.51.100.9")

        remaining = self.db.scalars(select(LoginAttempt.bucket)).all()
        self.assertEqual(remaining, ["198.51.100.9"])


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
