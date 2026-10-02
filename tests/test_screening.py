"""Cribar operaciones, exportarlas y recibir avisos: lo que se pide para usar
los datos, además de leerlos. Y los tramos y retrasos, a la vista."""

import unittest
from datetime import date, timedelta

from app import main
from app.amounts import volume_range
from app.models import Politician, Ticker, Trade
from tests.support import memory_session
from tests.test_public_pages import make_request


def filters(**values):
    defaults = dict(side=None, ticker=None, politician_id=None, category=None, min_amount=None, since_days=None)
    defaults.update(values)
    return main.TradeFilters(**defaults)


class ScreeningTests(unittest.TestCase):
    def setUp(self):
        self.db = memory_session()
        self.ana = Politician(name="Ana", chamber="House", state="WA", category="congress")
        self.ceo = Politician(name="Bea", chamber="CEO", state="Acme", category="business")
        self.acme = Ticker(symbol="ACME", name="Acme")
        self.nvda = Ticker(symbol="NVDA", name="Nvidia")
        self.db.add_all([self.ana, self.ceo, self.acme, self.nvda])
        self.db.flush()
        today = date.today()
        for person, ticker, kind, amount, days_ago in (
            (self.ana, self.acme, "Purchase", 75_000, 2),
            (self.ana, self.nvda, "Sale", 8_000, 3),
            (self.ceo, self.nvda, "Purchase", 1_000_000, 30),
            (self.ceo, self.acme, "Grant", 5_000_000, 1),
        ):
            self.db.add(Trade(politician_id=person.id, ticker_id=ticker.id, trade_type=kind,
                              amount=amount, reported_date=today - timedelta(days=days_ago),
                              transaction_date=today - timedelta(days=days_ago + 20)))
        self.db.flush()

    def tearDown(self):
        self.db.close()

    def tickers(self, **values):
        payload = main.get_trades(self.db, limit=100, offset=0, filters=filters(**values))
        return sorted((row["ticker"], row["trade_type"]) for row in payload["results"])

    def test_big_recent_buys(self):
        self.assertEqual(self.tickers(side="buy", min_amount=50_000, since_days=7), [("ACME", "Purchase")])

    def test_by_ticker_and_by_profile(self):
        self.assertEqual(len(self.tickers(ticker="nvda")), 2)
        self.assertEqual(self.tickers(category="business", side="buy"), [("NVDA", "Purchase")])
        self.assertEqual(len(self.tickers(politician_id=self.ana.id)), 2)

    def test_records_carry_the_lag(self):
        row = main.get_trades(self.db, limit=1, offset=0, filters=filters(ticker="ACME", side="buy"))["results"][0]
        self.assertEqual(row["disclosure_lag_days"], 20)
        self.assertEqual(row["side"], "buy")

    def test_csv_has_the_same_rows_and_the_bracket(self):
        response = main.export_trades_csv(self.db, limit=100, filters=filters(category="congress"))
        lines = response.body.decode().strip().splitlines()
        self.assertTrue(lines[0].startswith("id,reported_date"))
        self.assertEqual(len(lines), 3)
        self.assertIn("text/csv", response.media_type)

    def test_the_feed_is_atom_with_one_entry_per_trade(self):
        response = main.trades_feed(make_request("/feed.xml"), self.db, filters=filters(side="buy"))
        body = response.body.decode()
        self.assertIn('<feed xmlns="http://www.w3.org/2005/Atom">', body)
        self.assertEqual(body.count("<entry>"), 2)

    def test_the_api_rejects_unknown_sides(self):
        from tests.test_http import call

        status, _headers, _body = call("GET", "/api/trades", b"side=short")
        self.assertEqual(status, 422)


class BracketTests(unittest.TestCase):
    def test_the_range_behind_the_midpoints(self):
        # Dos operaciones de $1K-$15K y una de $15K-$50K.
        self.assertEqual(volume_range([8_000, 8_000, 32_500]), {"min": 17_003, "max": 80_000, "trades": 3})

    def test_the_top_bracket_has_no_ceiling(self):
        self.assertIsNone(volume_range([50_000_001])["max"])

    def test_exact_amounts_are_not_brackets(self):
        self.assertIsNone(volume_range([1234.5]))


class LagTests(unittest.TestCase):
    def test_the_profile_shows_lag_and_late_filings(self):
        db = memory_session()
        person = Politician(name="Ana", chamber="House", state="WA", category="congress")
        ticker = Ticker(symbol="ACME", name="Acme")
        db.add_all([person, ticker])
        db.flush()
        today = date.today()
        for lag in (10, 60):
            db.add(Trade(politician_id=person.id, ticker_id=ticker.id, trade_type="Purchase", amount=8_000 + lag,
                         reported_date=today - timedelta(days=1), transaction_date=today - timedelta(days=1 + lag)))
        db.flush()
        page = main.politician_detail_page(make_request(f"/politicians/{person.id}"), person.id, db)
        db.close()
        self.assertEqual(page.context["average_lag"], 35)
        self.assertEqual(page.context["late_filings"], 1)
        self.assertIn("declarada 60 días después", page.body.decode())
