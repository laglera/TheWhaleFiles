"""Páginas y respuestas que sólo existen porque la web sale al público:
las legales, lo que leen los buscadores, los errores con estilo y la API
paginada."""

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


class LegalPageTests(unittest.TestCase):
    def test_every_document_renders_in_both_languages(self):
        for doc in main.LEGAL_DOCS:
            for lang in ("es", "en"):
                response = main.legal_page(make_request(f"/legal/{doc}"), doc, lang, None)
                self.assertEqual(response.status_code, 200, f"{doc}/{lang}")

    def test_an_unknown_document_is_a_404(self):
        with self.assertRaises(HTTPException) as raised:
            main.legal_page(make_request("/legal/inventado"), "inventado", "es", None)
        self.assertEqual(raised.exception.status_code, 404)

    def test_the_financial_disclaimer_is_on_every_legal_page(self):
        # No basta con tenerlo escrito en una de ellas: es lo que alguien tiene
        # que leer antes de tomarse un número de esta web en serio.
        for doc in main.LEGAL_DOCS:
            html = main.legal_page(make_request(f"/legal/{doc}"), doc, "es", None).body.decode()
            self.assertIn("no es un asesor de inversiones", html.lower())

    def test_the_privacy_page_explains_how_to_delete_the_account(self):
        html = main.legal_page(make_request("/legal/privacy"), "privacy", "es", None).body.decode()
        self.assertIn("Borrar mi cuenta", html)


class IndexingTests(unittest.TestCase):
    def test_robots_keeps_crawlers_out_of_accounts_and_the_api(self):
        body = main.robots(make_request("/robots.txt"))
        self.assertIn("Disallow: /account", body)
        self.assertIn("Disallow: /api/", body)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", body)

    def test_the_sitemap_lists_the_home_page_and_the_legal_ones(self):
        db = next(get_db())
        try:
            xml = main.sitemap(make_request("/sitemap.xml"), db).body.decode()
        finally:
            db.close()
        self.assertIn("<loc>http://testserver/</loc>", xml)
        for doc in main.LEGAL_DOCS:
            self.assertIn(f"<loc>http://testserver/legal/{doc}</loc>", xml)


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
