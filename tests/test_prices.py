import unittest
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from app.models import PriceQuote
from app.prices import combine_positions


def holding(symbol, shares, name=None):
    return SimpleNamespace(
        shares=shares,
        as_of=date(2026, 6, 1),
        ticker=SimpleNamespace(symbol=symbol, name=name or symbol),
    )


NOW = datetime(2026, 8, 16, 13, 0)


def quote(symbol, price, previous_close=0.0, currency="USD", fetched_at=datetime(2026, 8, 16, 12, 0)):
    return PriceQuote(
        symbol=symbol,
        price=price,
        currency=currency,
        previous_close=previous_close,
        fetched_at=fetched_at,
    )


class CombinePositionsTests(unittest.TestCase):
    def test_values_positions_and_totals(self):
        result = combine_positions(
            [holding("TSLA", 1000), holding("AAPL", 500)],
            {"TSLA": quote("TSLA", 200.0), "AAPL": quote("AAPL", 100.0)},
        )
        self.assertEqual(result["total"], 250_000.0)
        self.assertEqual(result["valued"], 2)
        self.assertEqual(result["missing"], 0)

    def test_positions_without_a_quote_do_not_count_as_zero(self):
        # SpaceX aparece en los Form 4 de Musk pero no cotiza: valorarla a cero
        # rebajaría el patrimonio, y omitirla sin avisar lo daría por completo.
        result = combine_positions(
            [holding("TSLA", 1000), holding("SPCX", 800_000)],
            {"TSLA": quote("TSLA", 200.0)},
        )
        self.assertEqual(result["total"], 200_000.0)
        self.assertEqual(result["missing"], 1)
        without_price = [p for p in result["positions"] if p["symbol"] == "SPCX"][0]
        self.assertIsNone(without_price["value"])
        self.assertIsNone(without_price["price"])

    def test_sorted_by_value_with_unpriced_last(self):
        result = combine_positions(
            [holding("A", 1), holding("SPCX", 999), holding("B", 100)],
            {"A": quote("A", 10.0), "B": quote("B", 10.0)},
        )
        self.assertEqual([p["symbol"] for p in result["positions"]], ["B", "A", "SPCX"])

    def test_daily_change_is_computed_from_previous_close(self):
        result = combine_positions(
            [holding("TSLA", 10)], {"TSLA": quote("TSLA", 110.0, previous_close=100.0)}
        )
        self.assertAlmostEqual(result["positions"][0]["change_pct"], 10.0)

    def test_no_previous_close_leaves_change_undefined(self):
        result = combine_positions([holding("TSLA", 10)], {"TSLA": quote("TSLA", 110.0)})
        self.assertIsNone(result["positions"][0]["change_pct"])

    def test_empty_portfolio(self):
        result = combine_positions([], {})
        self.assertEqual(result["total"], 0.0)
        self.assertEqual(result["positions"], [])


class CurrencyTests(unittest.TestCase):
    def test_a_foreign_listing_is_converted_at_the_days_rate(self):
        # Antes se sumaba como si fueran dólares: 100 acciones a 50 EUR
        # contaban 5.000 USD fuera cual fuera el cambio.
        result = combine_positions(
            [holding("SAP.DE", 100), holding("AAPL", 10)],
            {"SAP.DE": quote("SAP.DE", 50, currency="EUR"), "AAPL": quote("AAPL", 100)},
            {"EUR": quote("EURUSD=X", 1.1)},
            now=NOW,
        )
        self.assertEqual(result["total"], 6500)
        self.assertEqual(result["converted"], 1)
        self.assertEqual(result["currency"], "USD")

    def test_without_an_exchange_rate_it_is_left_out_and_said_why(self):
        result = combine_positions(
            [holding("SAP.DE", 100), holding("AAPL", 10)],
            {"SAP.DE": quote("SAP.DE", 50, currency="EUR"), "AAPL": quote("AAPL", 100)},
            now=NOW,
        )
        self.assertEqual(result["total"], 1000)
        self.assertEqual(result["missing_fx"], 1)
        sap = [p for p in result["positions"] if p["symbol"] == "SAP.DE"][0]
        self.assertEqual(sap["missing_reason"], "fx")

    def test_london_pence_become_pounds(self):
        from decimal import Decimal

        from app.prices import normalise_currency

        self.assertEqual(normalise_currency("GBp"), ("GBP", Decimal(100)))
        self.assertEqual(normalise_currency("USD"), ("USD", Decimal(1)))
        self.assertEqual(normalise_currency(None), ("USD", Decimal(1)))

    def test_yahoo_keeps_the_currency_it_reports(self):
        from decimal import Decimal
        from unittest import mock

        from app import prices

        payload = {
            "chart": {
                "result": [
                    {"meta": {"regularMarketPrice": Decimal("412.5"), "chartPreviousClose": Decimal("400"),
                              "currency": "GBp", "longName": "Shell"}}
                ]
            }
        }
        with mock.patch.object(prices, "_get_json", return_value=payload):
            data = prices.fetch_from_yahoo("SHEL.L")
        self.assertEqual(data["currency"], "GBP")
        self.assertEqual(data["price"], Decimal("4.125"))


class StalenessTests(unittest.TestCase):
    def test_fresh_quotes_are_not_flagged(self):
        result = combine_positions([holding("AAPL", 1)], {"AAPL": quote("AAPL", 1)}, now=NOW)
        self.assertFalse(result["stale"])

    def test_a_quote_older_than_a_day_is_flagged(self):
        old = datetime(2026, 8, 13, 13, 0)
        result = combine_positions(
            [holding("AAPL", 1), holding("TSLA", 1)],
            {"AAPL": quote("AAPL", 1), "TSLA": quote("TSLA", 1, fetched_at=old)},
            now=NOW,
        )
        self.assertTrue(result["stale"])
        self.assertEqual(result["stale_hours"], 72)
        # La fecha que se enseña es la de la más vieja, no la de la más nueva.
        self.assertEqual(result["fetched_at"], old)

    def test_the_profile_warns_when_quotes_are_stale(self):
        from datetime import date as day

        from app import main
        from app.models import Holding, Politician, Ticker
        from app.runtime import utcnow
        from tests.support import memory_session
        from tests.test_public_pages import make_request
        from unittest import mock

        db = memory_session()
        person = Politician(name="Ana", chamber="CEO", state="Acme", category="business")
        ticker = Ticker(symbol="ACME", name="Acme")
        db.add_all([person, ticker])
        db.flush()
        db.add(Holding(politician_id=person.id, ticker_id=ticker.id, shares=10, as_of=day(2026, 6, 1)))
        db.flush()
        old = {"ACME": quote("ACME", 5, fetched_at=utcnow() - timedelta(days=3))}
        with mock.patch("app.prices.get_prices", side_effect=lambda symbols, refresh=False: {
            s: old[s] for s in symbols if s in old
        }):
            response = main.politician_detail_page(make_request(f"/politicians/{person.id}"), person.id, db)
        db.close()
        self.assertIn("stale-note", response.body.decode())


class ValueHoldingsTests(unittest.TestCase):
    def test_a_profile_never_waits_for_the_quote_provider(self):
        # Cada valor sin precio esperaba hasta medio minuto de reintentos
        # contra Yahoo dentro de la petición: la ficha de Buffett tardaba tres
        # minutos. Por defecto sólo se lee la caché.
        from unittest import mock

        from app import prices

        with mock.patch.object(prices, "fetch_quote", side_effect=AssertionError("red")):
            result = prices.value_holdings([holding("NOPRICE-XYZ", 10)])
        self.assertEqual(result["missing"], 1)


if __name__ == "__main__":
    unittest.main()
