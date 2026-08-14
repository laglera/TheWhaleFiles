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

    def test_parse_official_html_filing_extracts_transactions(self):
        html = """
        <html><body>
        <h1>Periodic Transaction Report</h1>
        <div class="filing">
            <div>Senator Alex Morgan</div>
            <div>Transaction 1</div>
            <div>Ticker: AAPL</div>
            <div>Type: Buy</div>
            <div>Amount: $15000</div>
            <div>Date: 2026-08-01</div>
        </div>
        <div class="filing">
            <div>Transaction 2</div>
            <div>Ticker: MSFT</div>
            <div>Type: Sell</div>
            <div>Amount: $24000</div>
            <div>Date: 2026-08-05</div>
        </div>
        </body></html>
        """

        from app.sources import parse_official_html_filing

        trades = parse_official_html_filing(html, politician_name="Alex Morgan")

        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0]["ticker"], "AAPL")
        self.assertEqual(trades[0]["trade_type"], "Buy")
        self.assertEqual(trades[1]["ticker"], "MSFT")
        self.assertEqual(trades[1]["trade_type"], "Sell")


if __name__ == "__main__":
    unittest.main()
