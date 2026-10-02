"""Rentabilidad de copiar a alguien: sólo con lo que se sabía al publicarse,
y medida con las métricas de riesgo de siempre."""

import math
import unittest
from datetime import date, timedelta
from decimal import Decimal

from app.performance import (
    Series,
    copy_positions,
    evaluate,
    max_drawdown,
    risk_metrics,
    spearman,
)


def sessions(count, start=date(2025, 1, 1)):
    return [start + timedelta(days=index) for index in range(count)]


def series(closes, start=date(2025, 1, 1)):
    return Series([(day, Decimal(str(close))) for day, close in zip(sessions(len(closes), start), closes)])


class StatisticsTests(unittest.TestCase):
    def test_drawdown_is_the_worst_fall_from_a_peak(self):
        self.assertAlmostEqual(max_drawdown([0.10, -0.5, 0.2]), -0.5)
        self.assertEqual(max_drawdown([0.01, 0.02]), 0.0)

    def test_spearman_of_a_monotonic_relation_is_one(self):
        self.assertAlmostEqual(spearman([1, 2, 3, 4], [10, 20, 35, 100]), 1.0)
        self.assertAlmostEqual(spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)

    def test_copying_the_index_has_beta_one_and_no_alpha(self):
        bench = [0.01 * math.sin(index) for index in range(300)]
        metrics = risk_metrics(bench, bench, rf=0.0)
        self.assertAlmostEqual(metrics["beta"], 1.0)
        self.assertAlmostEqual(metrics["alpha"], 0.0)
        self.assertAlmostEqual(metrics["correlation"], 1.0)
        self.assertAlmostEqual(metrics["tracking_error"], 0.0)
        self.assertIsNone(metrics["information_ratio"])


class CopyTests(unittest.TestCase):
    def test_entry_is_the_session_after_publication_not_the_trade_date(self):
        # Comprar el día en que se operó sería usar información que nadie tenía.
        prices = {"ACME": series([10, 11, 12, 13, 14, 15])}
        positions = copy_positions(
            [{"symbol": "ACME", "side": "buy", "reported": date(2025, 1, 2)}], prices, hold_sessions=2
        )
        self.assertEqual(positions[0]["entry"], 2)
        self.assertEqual(positions[0]["exit"], 4)

    def test_a_published_sale_closes_the_copy(self):
        prices = {"ACME": series([10] * 20)}
        positions = copy_positions(
            [
                {"symbol": "ACME", "side": "buy", "reported": date(2025, 1, 1)},
                {"symbol": "ACME", "side": "sell", "reported": date(2025, 1, 5)},
            ],
            prices,
            hold_sessions=10,
        )
        self.assertEqual(positions[0]["exit"], 5)
        self.assertTrue(positions[0]["closed_by_sale"])

    def test_a_sale_without_a_copy_does_not_short(self):
        prices = {"ACME": series([10] * 20)}
        positions = copy_positions(
            [{"symbol": "ACME", "side": "sell", "reported": date(2025, 1, 5)}], prices
        )
        self.assertEqual(positions, [])


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        days = 200
        # El índice sube un 0,05 % al día; ACME, el doble.
        self.bench = series([100 * 1.0005 ** index for index in range(days)])
        self.prices = {"ACME": series([10 * 1.001 ** index for index in range(days)])}

    def signals(self, count):
        return [
            {"symbol": "ACME", "side": "buy", "reported": date(2025, 1, 1) + timedelta(days=index * 10),
             "amount": 8000}
            for index in range(count)
        ]

    def test_a_handful_of_trades_publishes_nothing(self):
        result = evaluate(self.signals(3), self.prices, self.bench, hold_sessions=20)
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "few_trades")

    def test_beating_the_index_shows_as_excess_and_wins(self):
        result = evaluate(self.signals(10), self.prices, self.bench, hold_sessions=20, cost_bps=0)
        self.assertTrue(result["available"])
        self.assertGreater(result["total_return"], result["benchmark_return"])
        self.assertEqual(result["win_rate"], 1.0)
        self.assertGreaterEqual(result["sessions"], 60)

    def test_costs_lower_the_result(self):
        free = evaluate(self.signals(10), self.prices, self.bench, hold_sessions=20, cost_bps=0)
        costly = evaluate(self.signals(10), self.prices, self.bench, hold_sessions=20, cost_bps=50)
        self.assertLess(costly["total_return"], free["total_return"])

    def test_signals_without_prices_are_counted_apart(self):
        signals = self.signals(10) + [{"symbol": "NOPE", "side": "buy", "reported": date(2025, 2, 1)}]
        result = evaluate(signals, self.prices, self.bench, hold_sessions=20)
        self.assertEqual(result["signals"], 11)
        self.assertEqual(result["priced_signals"], 10)


class ProfileTests(unittest.TestCase):
    def test_the_profile_and_the_api_show_the_stored_result(self):
        import json

        from app import main
        from app.models import Performance
        from app.runtime import utcnow
        from tests.support import memory_session, seed_declarant
        from tests.test_public_pages import make_request

        db = memory_session()
        person = seed_declarant(db)
        result = evaluate(
            EvaluateTests.signals(EvaluateTests(), 10),
            {"ACME": series([10 * 1.001 ** index for index in range(200)])},
            series([100 * 1.0005 ** index for index in range(200)]),
            hold_sessions=20,
        )
        db.add(Performance(politician_id=person.id, computed_at=utcnow(), payload=json.dumps(result)))
        db.flush()
        page = main.politician_detail_page(make_request(f"/politicians/{person.id}"), person.id, db)
        api = main.get_politician_detail(person.id, db, limit=5, offset=0)
        db.close()
        body = page.body.decode()
        self.assertIn("¿Y si le hubieras copiado?", body)
        self.assertIn("Sharpe", body)
        self.assertTrue(api["performance"]["available"])
        json.dumps(api)  # serializable


if __name__ == "__main__":
    unittest.main()


class SchedulerTests(unittest.TestCase):
    """El hilo de polling tiene que dejar calculada la rentabilidad: si no, la
    sección no aparecía en ninguna ficha fuera del refresco de producción."""

    def setUp(self):
        import app.scheduler as scheduler

        self.scheduler = scheduler
        scheduler._last_performance = None

    def run_with(self, people, now):
        from unittest import mock

        with mock.patch("app.history.refresh_history", return_value={}) as history, mock.patch(
            "app.performance.compute_all", return_value={"people": people}
        ) as compute:
            result = self.scheduler.refresh_analytics(now)
        return result, history.call_count, compute.call_count

    def test_downloads_history_and_computes_once_a_day(self):
        from datetime import datetime

        start = datetime(2026, 10, 1, 8)
        self.assertEqual(self.run_with(10, start), (True, 1, 1))
        self.assertEqual(self.run_with(10, start + timedelta(hours=1)), (False, 1, 0))
        self.assertEqual(self.run_with(10, start + timedelta(hours=25)), (True, 1, 1))

    def test_without_the_index_it_retries_on_the_next_pass(self):
        from datetime import datetime

        start = datetime(2026, 10, 1, 8)
        self.assertEqual(self.run_with(0, start), (False, 1, 1))
        self.assertEqual(self.run_with(10, start + timedelta(minutes=15)), (True, 1, 1))
