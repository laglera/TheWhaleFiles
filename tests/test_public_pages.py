"""Páginas y respuestas que sólo existen porque la web sale al público: lo que
leen los buscadores, los errores con estilo y la API paginada."""

import unittest

from fastapi import HTTPException
from sqlalchemy import select
from starlette.requests import Request

from app import main
from app.database import get_db
from app.models import Politician


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
        db = next(get_db())
        try:
            xml = main.sitemap(make_request("/sitemap.xml"), db).body.decode()
            first = db.scalar(select(Politician.id).order_by(Politician.id))
        finally:
            db.close()
        self.assertIn("<loc>http://testserver/</loc>", xml)
        self.assertIn(f"<loc>http://testserver/politicians/{first}</loc>", xml)


class PaginationTests(unittest.TestCase):
    def setUp(self):
        self.db = next(get_db())

    def tearDown(self):
        self.db.close()

    def test_trades_come_capped_and_with_the_total(self):
        payload = main.get_trades(self.db, limit=5, offset=0)
        self.assertLessEqual(len(payload["results"]), 5)
        self.assertGreaterEqual(payload["total"], len(payload["results"]))

    def test_the_offset_moves_the_window(self):
        first = main.get_trades(self.db, limit=3, offset=0)["results"]
        second = main.get_trades(self.db, limit=3, offset=3)["results"]
        if first and second:
            self.assertNotEqual([row["id"] for row in first], [row["id"] for row in second])

    def test_politicians_carry_their_trade_count_without_a_query_each(self):
        payload = main.get_politicians(self.db, limit=5, offset=0)
        for row in payload["results"]:
            self.assertIsInstance(row["trade_count"], int)

    def test_a_profile_returns_its_trades_capped(self):
        politician = self.db.scalar(select(Politician).order_by(Politician.id))
        payload = main.get_politician_detail(politician.id, self.db, limit=4, offset=0)
        self.assertLessEqual(len(payload["trades"]), 4)
        self.assertIn("total_trades", payload)


class DatabaseUrlTests(unittest.TestCase):
    def test_a_trailing_newline_does_not_travel_into_the_host(self):
        # Pasar la cadena de un fichero a un gestor de secretos con una tubería
        # se lleva el salto de línea pegado al valor.
        from app.database import resolve_database_url

        self.assertEqual(
            resolve_database_url("postgresql://u:c@host/base\n"),
            "postgresql://u:c@host/base",
        )

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
