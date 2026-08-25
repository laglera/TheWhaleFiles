import unittest
from datetime import date, timedelta

from sqlalchemy import text

from app.database import get_engine
from app.ingestion import load_filing_into_db, load_trade_records_into_db
from app.models import Base


class IngestionTests(unittest.TestCase):
    def test_load_filing_into_db_stores_trade_records(self):
        database_url = "sqlite:///:memory:"
        engine = get_engine(database_url)
        Base.metadata.create_all(bind=engine)

        raw_text = """
        Senate Financial Disclosure - Periodic Transaction Report

        Politician: Alex Morgan
        Office: Senate
        State: California

        Transaction 1:
        Ticker: AAPL
        Type: Buy
        Amount: $15,000
        Date: 2026-07-12

        Transaction 2:
        Ticker: NVDA
        Type: Buy
        Amount: $25,000
        Date: 2026-07-18
        """

        inserted = load_filing_into_db(raw_text, "Alex Morgan", database_url=database_url)

        self.assertEqual(len(inserted), 2)
        self.assertEqual(inserted[0]["ticker"], "AAPL")
        self.assertEqual(inserted[1]["ticker"], "NVDA")

        with engine.begin() as conn:
            politician_count = conn.execute(text("SELECT COUNT(*) FROM politicians")).scalar()
            ticker_count = conn.execute(text("SELECT COUNT(*) FROM tickers")).scalar()
            trade_count = conn.execute(text("SELECT COUNT(*) FROM trades")).scalar()

        self.assertEqual(politician_count, 1)
        self.assertEqual(ticker_count, 2)
        self.assertEqual(trade_count, 2)


class TradeDateTests(unittest.TestCase):
    """Las dos fechas de un filing: cuándo se operó y cuándo se hizo público."""

    def setUp(self):
        self.database_url = f"sqlite:///:memory:?ingest={self.id()}"
        self.engine = get_engine(self.database_url)
        Base.metadata.create_all(bind=self.engine)

    def _load(self, **overrides):
        record = {
            "politician_name": "Mike Kelly",
            "ticker": "ABT",
            "trade_type": "Sale",
            "amount": 8000.0,
            "reported_date": "2026-08-12",
            "transaction_date": "2026-07-17",
        }
        record.update(overrides)
        return load_trade_records_into_db([record], database_url=self.database_url)

    def _stored_dates(self):
        with self.engine.begin() as conn:
            return conn.execute(
                text("SELECT reported_date, transaction_date FROM trades")
            ).all()

    def test_both_dates_are_stored(self):
        self.assertEqual(len(self._load()), 1)
        self.assertEqual(self._stored_dates(), [("2026-08-12", "2026-07-17")])

    def test_a_filing_published_in_the_future_is_dropped(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        self.assertEqual(self._load(reported_date=tomorrow), [])
        self.assertEqual(self._stored_dates(), [])

    def test_a_trade_dated_after_its_own_filing_is_stored_without_that_date(self):
        # El caso real que sacó esto a la luz: un PTR publicado en enero de 2026
        # que declaraba una compra fechada en diciembre de 2026. El año está mal
        # escrito en el filing y no hay forma de saber cuál era; la operación se
        # guarda, la fecha imposible no.
        saved = self._load(reported_date="2026-01-21", transaction_date="2026-12-26")

        self.assertEqual(len(saved), 1)
        self.assertIsNone(saved[0]["transaction_date"])
        self.assertEqual(self._stored_dates(), [("2026-01-21", None)])

    def test_a_trade_without_a_transaction_date_is_still_stored(self):
        saved = self._load(transaction_date=None)

        self.assertEqual(len(saved), 1)
        self.assertIsNone(saved[0]["transaction_date"])
        self.assertEqual(self._stored_dates(), [("2026-08-12", None)])

    def test_the_same_record_is_not_imported_twice(self):
        self._load()
        self.assertEqual(self._load(), [])

    def test_two_trades_of_the_same_filing_on_different_days_both_survive(self):
        # Misma persona, mismo valor, mismo importe y misma publicación: sólo
        # las distingue el día en que se ejecutaron. Con la identidad anterior,
        # la segunda se descartaba como duplicada.
        self._load(transaction_date="2026-07-17")
        self._load(transaction_date="2026-07-20")

        self.assertEqual(len(self._stored_dates()), 2)


if __name__ == "__main__":
    unittest.main()
