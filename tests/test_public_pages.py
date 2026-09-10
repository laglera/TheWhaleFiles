"""Páginas y respuestas que sólo existen porque la web sale al público: lo que
leen los buscadores, los errores con estilo y la API paginada."""

import unittest

from fastapi import HTTPException
from starlette.requests import Request

from app import main
from tests.support import memory_session, seed_declarant


def make_request(path="/", query=b""):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": ("testserver", 80),
            "path": path,
            "query_string": query,
            "headers": [],
            "client": ("203.0.113.7", 5000),
        }
    )


class IndexingTests(unittest.TestCase):
    def test_robots_keeps_crawlers_out_of_the_api(self):
        body = main.robots(make_request("/robots.txt"))
        self.assertIn("Disallow: /api/", body)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", body)

    def test_the_sitemap_lists_the_home_page_and_the_profiles(self):
        db = memory_session()
        try:
            person = seed_declarant(db)
            xml = main.sitemap(make_request("/sitemap.xml"), db).body.decode()
        finally:
            db.close()
        self.assertIn("<loc>http://testserver/</loc>", xml)
        self.assertIn(f"<loc>http://testserver/politicians/{person.id}</loc>", xml)

    def test_the_sitemap_leaves_out_profiles_without_trades(self):
        # Una ficha vacía no le aporta nada a quien llega desde un buscador,
        # y el sitemap la filtra con un join que la prueba anterior no veía:
        # sembraba operaciones para todos.
        db = memory_session()
        try:
            silent = seed_declarant(db, name="Robin Vega", trades=0)
            xml = main.sitemap(make_request("/sitemap.xml"), db).body.decode()
        finally:
            db.close()
        self.assertNotIn(f"/politicians/{silent.id}<", xml)


class PaginationTests(unittest.TestCase):
    def setUp(self):
        self.db = memory_session()
        self.person = seed_declarant(self.db)

    def tearDown(self):
        self.db.close()

    def test_trades_come_capped_and_with_the_total(self):
        payload = main.get_trades(self.db, limit=5, offset=0)
        self.assertLessEqual(len(payload["results"]), 5)
        self.assertGreaterEqual(payload["total"], len(payload["results"]))

    def test_the_offset_moves_the_window(self):
        # Con datos propios el desplazamiento se comprueba de verdad: antes,
        # sobre una base que podía estar vacía, el "if" dejaba pasar la prueba
        # sin haber comparado nada.
        first = main.get_trades(self.db, limit=3, offset=0)["results"]
        second = main.get_trades(self.db, limit=3, offset=3)["results"]
        self.assertEqual(len(first), 3)
        self.assertEqual(len(second), 3)
        self.assertNotEqual([row["id"] for row in first], [row["id"] for row in second])

    def test_politicians_carry_their_trade_count_without_a_query_each(self):
        payload = main.get_politicians(self.db, limit=5, offset=0)
        for row in payload["results"]:
            self.assertIsInstance(row["trade_count"], int)

    def test_a_profile_returns_its_trades_capped(self):
        payload = main.get_politician_detail(self.person.id, self.db, limit=4, offset=0)
        self.assertEqual(len(payload["trades"]), 4)
        self.assertEqual(payload["total_trades"], 6)


class DatabaseUrlTests(unittest.TestCase):
    def test_a_trailing_newline_does_not_travel_into_the_host(self):
        # Pasar la cadena de un fichero a un gestor de secretos con una tubería
        # se lleva el salto de línea pegado al valor.
        from app.database import resolve_database_url

        self.assertEqual(
            resolve_database_url("postgresql://u:c@host/base\n"),
            "postgresql://u:c@host/base",
        )

    def test_the_console_command_copied_from_the_panel_still_connects(self):
        # Neon ofrece la cadena como `psql '…'`, y el .env la trae con su
        # nombre delante: las dos se pegan enteras en el gestor de secretos.
        from app.database import resolve_database_url

        expected = "postgresql://u:c@host/base?sslmode=require"
        for pasted in (
            "psql 'postgresql://u:c@host/base?sslmode=require'",
            '"postgresql://u:c@host/base?sslmode=require"',
            "DATABASE_URL=postgresql://u:c@host/base?sslmode=require",
            "DATABASE_URL='postgres://u:c@host/base?sslmode=require'\n",
        ):
            self.assertEqual(resolve_database_url(pasted), expected, pasted)

    def test_ingestion_writes_to_the_configured_database(self):
        # Sin URL explícita caía en un SQLite fijo aunque DATABASE_URL
        # apuntara a Postgres, y producción nunca recibía las operaciones.
        from unittest import mock

        from sqlalchemy import text

        from app import ingestion
        from app.database import get_engine

        configured = "sqlite:///:memory:?configured=ingestion"
        record = {
            "politician_name": "Robin Vega",
            "ticker": "ACME",
            "trade_type": "Purchase",
            "amount": 8000.0,
            "reported_date": "2026-03-01",
        }
        with mock.patch.object(ingestion, "DATABASE_URL", configured):
            ingestion.load_trade_records_into_db([record])

        with get_engine(configured).connect() as connection:
            stored = connection.execute(text("SELECT COUNT(*) FROM trades")).scalar()
        self.assertEqual(stored, 1)

    def test_the_old_postgres_scheme_is_still_translated(self):
        from app.database import resolve_database_url

        self.assertEqual(
            resolve_database_url("  postgres://u:c@host/base  "),
            "postgresql://u:c@host/base",
        )


class AdminEndpointTests(unittest.TestCase):
    def test_the_sample_loader_is_closed_without_a_token(self):
        # Escribía en la base operaciones de un político inventado, y estaba
        # abierto a cualquiera con curl.
        with self.assertRaises(HTTPException) as raised:
            main.load_sample_filing(make_request("/api/load-sample-filing"))
        self.assertEqual(raised.exception.status_code, 404)

    def test_the_polling_endpoint_is_closed_without_a_token(self):
        with self.assertRaises(HTTPException) as raised:
            main.poll_sources_endpoint(make_request("/api/poll-sources"))
        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
