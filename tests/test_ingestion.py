import unittest

from sqlalchemy import text

from app.database import get_engine
from app.ingestion import load_filing_into_db
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


if __name__ == "__main__":
    unittest.main()
