import unittest
from pathlib import Path

from app.scraper import parse_senate_filing


class ScraperParsingTests(unittest.TestCase):
    def test_parse_senate_filing_extracts_transactions(self):
        sample = Path("app/data/sample_senate_filing.txt").read_text(encoding="utf-8")

        trades = parse_senate_filing(sample, politician_name="Alex Morgan")

        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0]["ticker"], "AAPL")
        self.assertEqual(trades[0]["trade_type"], "Buy")
        self.assertEqual(trades[0]["amount"], 15000.0)
        self.assertEqual(trades[1]["ticker"], "NVDA")
        self.assertEqual(trades[1]["trade_type"], "Buy")
        self.assertEqual(trades[1]["amount"], 25000.0)


if __name__ == "__main__":
    unittest.main()
