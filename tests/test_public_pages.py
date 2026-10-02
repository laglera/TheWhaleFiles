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


class PublicUrlTests(unittest.TestCase):
    def test_the_configured_public_url_wins_over_the_request_host(self):
        # Desde local el sitemap publicaba "http://127.0.0.1:8765/…", y detrás
        # de un proxy salía http aunque el público entre por https.
        from unittest import mock

        db = memory_session()
        try:
            person = seed_declarant(db)
            with mock.patch.object(main, "SITE_BASE_URL", "https://thewhalefiles.example"):
                xml = main.sitemap(make_request("/sitemap.xml"), db).body.decode()
                robots = main.robots(make_request("/robots.txt"))
                html = main.politician_detail_page(
                    make_request(f"/politicians/{person.id}"), person.id, db
                ).body.decode()
        finally:
            db.close()
        self.assertIn(f"<loc>https://thewhalefiles.example/politicians/{person.id}</loc>", xml)
        self.assertNotIn("testserver", xml)
        self.assertIn("Sitemap: https://thewhalefiles.example/sitemap.xml", robots)
        self.assertIn(
            f'<meta property="og:url" content="https://thewhalefiles.example/politicians/{person.id}" />',
            html,
        )


class HomePageTests(unittest.TestCase):
    def setUp(self):
        self.db = memory_session()

    def tearDown(self):
        self.db.close()

    def add(self, name, trade_type, amount, day, symbol="ACME"):
        from datetime import date

        from sqlalchemy import select

        from app.models import Politician, Ticker, Trade

        person = self.db.scalar(select(Politician).where(Politician.name == name))
        if person is None:
            person = Politician(name=name, chamber="CEO", state="Acme", category="business")
            self.db.add(person)
            self.db.flush()
        ticker = self.db.scalar(select(Ticker).where(Ticker.symbol == symbol))
        if ticker is None:
            ticker = Ticker(symbol=symbol, name=symbol)
            self.db.add(ticker)
            self.db.flush()
        self.db.add(
            Trade(
                politician_id=person.id,
                ticker_id=ticker.id,
                trade_type=trade_type,
                amount=amount,
                reported_date=date(2026, 8, day),
            )
        )
        self.db.flush()

    def home(self):
        return main.home(make_request("/"), self.db)

    def test_the_hero_shows_five_people_even_after_a_long_filing(self):
        # Un directivo vendiendo por tramos llenaba las doce operaciones más
        # recientes, y el panel repetía su nombre cuatro veces de cinco.
        for index in range(30):
            self.add("Brian Chesky", "Sale", 1_000_000 + index, 20)
        for index, name in enumerate(["Ana", "Bea", "Carla", "Dora"]):
            self.add(name, "Purchase", 5_000, 10 - index)

        names = [trade.politician.name for trade in self.home().context["hero_trades"]]
        self.assertEqual(len(names), 5)
        self.assertEqual(len(set(names)), 5)

    def test_a_filing_dated_in_the_future_is_not_the_latest(self):
        # En producción abría la portada una compra "publicada" el 26/12/2026:
        # un error de escritura del documento original.
        from datetime import date, timedelta

        from sqlalchemy import select

        from app.models import Trade

        self.add("Ana", "Purchase", 5_000, 3)
        future = self.db.scalar(select(Trade))
        future.reported_date = date.today() + timedelta(days=90)
        self.add("Bea", "Purchase", 5_000, 2)

        context = self.home().context
        self.assertEqual([trade.politician.name for trade in context["recent_trades"]], ["Bea"])
        self.assertNotEqual(context["last_reported"], future.reported_date)
        self.assertEqual(main.get_trades(self.db, limit=10, offset=0)["total"], 1)

    def test_grants_do_not_count_as_declared_volume(self):
        self.add("Elon Musk", "Grant", 141_000_000_000, 1, symbol="TSLA")
        self.add("Elon Musk", "Sale", 2_000, 2, symbol="TSLA")
        self.add("Ana", "Purchase", 5_000, 3)

        context = self.home().context
        self.assertEqual(context["total_amount"], 7_000.0)
        # Ordenados por lo que compran y venden, no por lo que les conceden.
        self.assertEqual([person["name"] for person in context["politicians"]], ["Ana", "Elon Musk"])
        self.assertNotIn("Grant", [trade.trade_type for trade in context["hero_trades"]])

    def profile(self, name):
        from sqlalchemy import select

        from app.models import Politician

        person = self.db.scalar(select(Politician).where(Politician.name == name))
        return main.politician_detail_page(make_request(f"/politicians/{person.id}"), person.id, self.db)

    def test_the_profile_says_how_much_was_left_out_of_volume(self):
        # El volumen excluye la concesión, pero callarla también desinforma:
        # la ficha dice cuánto quedó fuera y reparte compras y ventas por importe.
        self.add("Elon Musk", "Grant", 141_000_000_000, 1, symbol="TSLA")
        self.add("Elon Musk", "Sale", 2_000_000, 2, symbol="TSLA")
        self.add("Elon Musk", "Purchase", 999_960_000, 3, symbol="TSLA")

        response = self.profile("Elon Musk")
        context = response.context
        self.assertEqual(context["total_amount"], 1_001_960_000.0)
        self.assertEqual(context["side_volume"]["other"], 141_000_000_000.0)
        html = response.body.decode()
        self.assertIn("$141.0B", html)
        self.assertIn("$1.0B comprados", html)

    def test_a_trade_without_amount_is_not_shown_as_zero(self):
        self.add("Ana", "Gift", 0, 1)
        html = self.profile("Ana").body.decode()
        self.assertIn("importe no declarado", html)
        self.assertNotIn('class="ledger__amount">$0<', html)


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


class DisclosureDeadlineTests(unittest.TestCase):
    """El plazo de 45 días de la STOCK Act, y los retrasos que no se creen."""

    def setUp(self):
        from datetime import date, timedelta

        from app.models import Ticker, Trade

        self.db = memory_session()
        self.person = seed_declarant(self.db, trades=0)
        self.person.category = "congress"
        ticker_id = self.db.query(Ticker.id).scalar()
        reported = date(2025, 5, 15)
        for amount, lag in ((8000, 10), (15000, 60), (32500, 3660)):
            self.db.add(
                Trade(
                    politician_id=self.person.id,
                    ticker_id=ticker_id,
                    trade_type="Purchase",
                    amount=amount,
                    reported_date=reported,
                    transaction_date=reported - timedelta(days=lag),
                )
            )
        self.db.flush()

    def tearDown(self):
        self.db.close()

    def test_each_trade_says_if_it_was_late_or_its_date_is_doubtful(self):
        flags = {
            trade["amount"]: (trade["late_filing"], trade["date_suspect"])
            for trade in main.get_politician_detail(self.person.id, self.db, limit=10, offset=0)["trades"]
        }
        self.assertEqual(flags, {8000: (False, False), 15000: (True, False), 32500: (False, True)})

    def test_a_ten_year_delay_does_not_drag_the_average(self):
        response = main.politician_detail_page(
            make_request(f"/politicians/{self.person.id}"), self.person.id, self.db
        )
        context = response.context
        self.assertEqual(context["average_lag"], 35)
        self.assertEqual((context["late_filings"], context["suspect_dates"]), (1, 1))
        html = response.body.decode()
        self.assertIn("fuera de plazo STOCK Act", html)
        self.assertIn("fecha dudosa", html)
        self.assertIn("Operada el", html)
