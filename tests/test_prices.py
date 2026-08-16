import unittest
from datetime import date, datetime
from types import SimpleNamespace

from app.models import PriceQuote
from app.prices import combine_positions


def holding(symbol, shares, name=None):
    return SimpleNamespace(
        shares=shares,
        as_of=date(2026, 6, 1),
        ticker=SimpleNamespace(symbol=symbol, name=name or symbol),
    )


def quote(symbol, price, previous_close=0.0):
    return PriceQuote(
        symbol=symbol,
        price=price,
        currency="USD",
        previous_close=previous_close,
        fetched_at=datetime(2026, 8, 16, 12, 0),
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


if __name__ == "__main__":
    unittest.main()
