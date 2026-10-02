"""Histórico de Yahoo: cierres ajustados, splits y dividendos, y su efecto
sobre las posiciones declaradas antes de ellos."""

import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.history import (
    decode_closes,
    dividends_since,
    encode_closes,
    history_universe,
    parse_chart,
    refresh_order,
    split_factor,
    store_history,
)
from app.models import CorporateAction, PriceHistory
from app.prices import combine_positions
from tests.support import memory_session
from tests.test_prices import NOW, holding, quote

# 2024-06-07 y 2024-06-10 a las 13:30 UTC; Nueva York va 4 horas por detrás.
FRIDAY, MONDAY = 1717767000, 1718026200
CHART = {
    "chart": {
        "result": [
            {
                "meta": {"currency": "USD", "gmtoffset": -14400},
                "timestamp": [FRIDAY, MONDAY],
                "indicators": {
                    "quote": [{"close": [Decimal("1208.88"), Decimal("121.79")]}],
                    "adjclose": [{"adjclose": [Decimal("120.87"), Decimal("121.77")]}],
                },
                "events": {
                    "splits": {str(MONDAY): {"date": MONDAY, "numerator": 10, "denominator": 1}},
                    "dividends": {str(FRIDAY): {"date": FRIDAY, "amount": Decimal("0.004")}},
                },
            }
        ]
    }
}


def action(kind, day, ratio=None, amount=None):
    return SimpleNamespace(kind=kind, day=day, ratio=ratio, amount=amount)


class ParseTests(unittest.TestCase):
    def test_adjusted_closes_and_events(self):
        parsed = parse_chart(CHART)
        self.assertEqual(parsed["bars"][0], (date(2024, 6, 7), Decimal("120.87")))
        self.assertEqual(parsed["splits"], [(date(2024, 6, 10), Decimal(10))])
        self.assertEqual(parsed["dividends"], [(date(2024, 6, 7), Decimal("0.004"))])

    def test_empty_answers_are_nothing(self):
        self.assertIsNone(parse_chart(None))
        self.assertIsNone(parse_chart({"chart": {"result": []}}))

    def test_closes_round_trip_without_floats(self):
        bars = [(date(2024, 1, 2), Decimal("187.150001"))]
        self.assertEqual(decode_closes(encode_closes(bars)), bars)


class AdjustmentTests(unittest.TestCase):
    def test_a_split_after_the_balance_multiplies_the_shares(self):
        # El Form 4 de 2023 de NVIDIA, contado tal cual tras el 10 por 1,
        # valía la décima parte.
        actions = [action("split", date(2024, 6, 10), ratio=Decimal(10))]
        self.assertEqual(split_factor(actions, date(2023, 1, 1)), 10)
        self.assertEqual(split_factor(actions, date(2025, 1, 1)), 1)

    def test_dividends_after_the_balance_add_up(self):
        actions = [
            action("dividend", date(2024, 3, 1), amount=Decimal("0.01")),
            action("dividend", date(2024, 6, 1), amount=Decimal("0.01")),
        ]
        self.assertEqual(dividends_since(actions, date(2024, 4, 1)), Decimal("0.01"))

    def test_valuation_uses_post_split_shares_and_reports_dividends(self):
        old = holding("NVDA", 100)
        old.as_of = date(2023, 6, 1)
        actions = {
            "NVDA": [
                action("split", date(2024, 6, 10), ratio=Decimal(10)),
                action("dividend", date(2024, 9, 1), amount=Decimal("0.5")),
            ]
        }
        result = combine_positions([old], {"NVDA": quote("NVDA", 100)}, now=NOW, actions=actions)
        self.assertEqual(result["total"], 100_000)
        self.assertEqual(result["dividends"], 500)
        self.assertEqual(result["split_adjusted"], 1)
        self.assertEqual(result["positions"][0]["shares_now"], 1000)


class StorageTests(unittest.TestCase):
    def test_store_keeps_bars_and_events_once(self):
        db = memory_session()
        parsed = parse_chart(CHART)
        # Dentro de la ventana que se guarda.
        recent = date.today() - timedelta(days=10)
        parsed["bars"] = [(recent, Decimal("10")), (recent + timedelta(days=1), Decimal("11"))]
        store_history(db, "NVDA", parsed, datetime(2026, 1, 1))
        store_history(db, "NVDA", parsed, datetime(2026, 1, 2))
        db.flush()
        row = db.query(PriceHistory).one()
        self.assertEqual(len(decode_closes(row.closes)), 2)
        self.assertEqual(db.query(CorporateAction).count(), 2)
        db.close()

    def test_unknown_symbols_are_remembered_and_not_retried_first(self):
        db = memory_session()
        store_history(db, "ZZZZ", None, datetime(2026, 1, 1))
        db.flush()
        order = refresh_order(db, ["SPY", "AAPL", "ZZZZ"], datetime(2026, 1, 2))
        self.assertEqual(order, ["SPY", "AAPL", "ZZZZ"])
        db.close()

    def test_the_universe_has_the_benchmark_and_recent_trades(self):
        from tests.support import seed_declarant

        db = memory_session()
        seed_declarant(db)
        self.assertEqual(history_universe(db, since=date(2020, 1, 1)), ["ACME", "SPY"])
        db.close()


if __name__ == "__main__":
    unittest.main()
