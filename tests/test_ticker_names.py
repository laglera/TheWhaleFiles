"""Nombre de empresa para los valores que sólo tenían el símbolo."""

import unittest
from unittest import mock

from app.models import Ticker
from app.ticker_names import fill_ticker_names, parse_sec_tickers
from tests.support import memory_session


SEC_PAYLOAD = {
    "0": {"cik_str": 1, "ticker": "PG", "title": "PROCTER & GAMBLE Co"},
    "1": {"cik_str": 2, "ticker": "BRK-B", "title": "BERKSHIRE HATHAWAY INC"},
    "2": {"cik_str": 2, "ticker": "BRK-A", "title": "BERKSHIRE HATHAWAY INC"},
}


class TickerNameTests(unittest.TestCase):
    def test_share_classes_match_with_dot_or_dash(self):
        names = parse_sec_tickers(SEC_PAYLOAD)
        self.assertEqual(names["BRK-B"], "BERKSHIRE HATHAWAY INC")

    def test_only_tickers_without_a_name_are_filled(self):
        db = memory_session()
        db.add_all(
            [
                Ticker(symbol="PG", name="PG"),
                Ticker(symbol="BRK.B", name="BRK.B"),
                Ticker(symbol="ACME", name="Acme Corp"),
                Ticker(symbol="GONE", name="GONE"),
            ]
        )
        db.commit()
        with mock.patch("app.ticker_names.SessionLocal", return_value=db), mock.patch(
            "app.ticker_names.prepare_database"
        ):
            stats = fill_ticker_names(parse_sec_tickers(SEC_PAYLOAD), verbose=False)
        names = dict(db.query(Ticker.symbol, Ticker.name).all())
        db.close()
        self.assertEqual(stats, {"missing": 3, "named": 2})
        self.assertEqual(names["PG"], "PROCTER & GAMBLE Co")
        self.assertEqual(names["BRK.B"], "BERKSHIRE HATHAWAY INC")
        # Lo que ya tenía nombre no se toca; lo que no cotiza se queda igual.
        self.assertEqual(names["ACME"], "Acme Corp")
        self.assertEqual(names["GONE"], "GONE")
