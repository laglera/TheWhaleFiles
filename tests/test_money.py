"""Importes, títulos y precios en Decimal: lo que se guarda es lo que se
declaró, y lo que se multiplica no arrastra errores de coma flotante."""

import unittest
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.types import Float, Numeric

from app.database import numeric_migrations
from app.models import Holding, Politician, PriceQuote, Ticker, Trade
from app.money import money, to_decimal
from app.prices import combine_positions
from app.runtime import utcnow
from tests.support import memory_session


class ConversionTests(unittest.TestCase):
    def test_floats_go_through_their_shortest_decimal_form(self):
        # Decimal(0.1) arrastra 55 decimales de ruido binario.
        self.assertEqual(to_decimal(0.1), Decimal("0.1"))
        self.assertEqual(to_decimal("1,234.5678", 2), Decimal("1234.57"))

    def test_rubbish_is_not_a_number(self):
        for value in (None, "", "abc", "NaN", float("inf"), True):
            self.assertIsNone(to_decimal(value), value)

    def test_money_is_to_the_cent(self):
        self.assertEqual(money(Decimal("2.005")), Decimal("2.01"))
        self.assertEqual(money(None), Decimal("0"))


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.db = memory_session()
        self.person = Politician(name="Ana", chamber="CEO", state="Acme", category="business")
        self.ticker = Ticker(symbol="BRK.B", name="Berkshire")
        self.db.add_all([self.person, self.ticker])
        self.db.flush()

    def tearDown(self):
        self.db.close()

    def test_amounts_come_back_as_the_declared_decimal(self):
        self.db.add(
            Trade(
                politician_id=self.person.id,
                ticker_id=self.ticker.id,
                trade_type="Sale",
                amount=Decimal("1234.56"),
                reported_date=date(2026, 3, 1),
            )
        )
        self.db.commit()
        self.db.expire_all()
        stored = self.db.scalar(select(Trade.amount))
        self.assertIsInstance(stored, Decimal)
        self.assertEqual(stored, Decimal("1234.56"))

    def test_large_positions_are_valued_exactly(self):
        # 12 millones de títulos B a 412,37: el producto exacto, no su
        # aproximación binaria.
        holding = Holding(
            politician_id=self.person.id,
            ticker_id=self.ticker.id,
            shares=Decimal("12345678.123456"),
            as_of=date(2026, 7, 1),
        )
        self.db.add(holding)
        self.db.add(
            PriceQuote(symbol="BRK.B", price=Decimal("412.370001"), fetched_at=utcnow())
        )
        self.db.commit()
        self.db.expire_all()
        holding = self.db.scalar(select(Holding))
        quote = self.db.scalar(select(PriceQuote))
        wealth = combine_positions([holding], {"BRK.B": quote})
        expected = Decimal("12345678.123456") * Decimal("412.370001")
        self.assertEqual(wealth["total"], expected)
        self.assertIsInstance(wealth["positions"][0]["value"], Decimal)


class IngestionIdentityTests(unittest.TestCase):
    def test_a_fractional_amount_is_recognised_on_the_next_pass(self):
        # Con float, 1234.56 leído de la base y 1234.56 recién parseado no
        # siempre eran el mismo número, y la segunda pasada lo reinsertaba.
        from app.ingestion import load_trade_records_into_db

        url = "sqlite:///:memory:?decimal=identity"
        record = {
            "politician_name": "Robin Vega",
            "ticker": "ACME",
            "trade_type": "Sale",
            "amount": 1234.56,
            "reported_date": (date.today() - timedelta(days=3)).isoformat(),
        }
        self.assertEqual(len(load_trade_records_into_db([record], database_url=url)), 1)
        self.assertEqual(load_trade_records_into_db([record], database_url=url), [])


class FakeInspector:
    def __init__(self, columns):
        self.columns = columns

    def get_table_names(self):
        return list(self.columns)

    def get_columns(self, table):
        return [{"name": name, "type": kind} for name, kind in self.columns[table].items()]


class MigrationTests(unittest.TestCase):
    def test_postgres_float_columns_become_numeric(self):
        inspector = FakeInspector(
            {
                "trades": {"amount": Float()},
                "holdings": {"shares": Numeric(24, 6)},
                "price_quotes": {"price": Float(), "previous_close": Float()},
            }
        )
        statements = numeric_migrations(inspector, "postgresql")
        self.assertEqual(len(statements), 3)
        self.assertIn(
            "ALTER TABLE trades ALTER COLUMN amount TYPE NUMERIC(19,4) USING amount::NUMERIC(19,4)",
            statements,
        )
        # La que ya es NUMERIC no se toca.
        self.assertFalse(any("holdings" in statement for statement in statements))

    def test_sqlite_is_left_alone(self):
        inspector = FakeInspector({"trades": {"amount": Float()}})
        self.assertEqual(numeric_migrations(inspector, "sqlite"), [])


if __name__ == "__main__":
    unittest.main()
