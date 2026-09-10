"""Tramos de importe del Congreso: cómo se guardan y cómo se enseñan."""

import json
import tempfile
import unittest

from sqlalchemy import text

from app.amounts import bracket_label, congress_amount
from app.database import get_engine


class BracketTests(unittest.TestCase):
    def test_a_clipped_bracket_is_the_same_bracket(self):
        # "$15,001" es un PDF recortado, no una operación de 15.001 dólares:
        # antes valía eso, y la misma operación completa valía 32.500.
        full = congress_amount("$15,001 - $50,000", 32500)
        self.assertEqual(congress_amount("$15,001", 15001), full)
        self.assertEqual(congress_amount("$15,001 -", 15001), full)
        self.assertEqual(full, 32500.0)

    def test_exact_amounts_keep_the_value_already_stored(self):
        # Cambiarlo haría que la siguiente pasada duplicara la operación.
        self.assertEqual(congress_amount("$848.75", 848), 848.0)

    def test_the_bracket_is_shown_instead_of_its_midpoint(self):
        self.assertEqual(bracket_label(8000), "$1K–$15K")
        self.assertEqual(bracket_label(32500), "$15K–$50K")
        self.assertEqual(bracket_label(750000), "$500K–$1M")
        self.assertEqual(bracket_label(3000000), "$1M–$5M")
        self.assertEqual(bracket_label(50000001), ">$50M")
        self.assertIsNone(bracket_label(848))


class RepairTests(unittest.TestCase):
    def record(self, amount, amount_mid, ticker="ABT", day="12"):
        return {
            "transaction_date": "07/17/2026",
            "disclosure_date": f"08/{day}/2026",
            "ticker": ticker,
            "type": "Sale",
            "amount": amount,
            "amount_mid": amount_mid,
            "representative": "Mike Kelly",
            "district": "PA16",
        }

    def test_stored_lower_bounds_move_to_the_midpoint_without_duplicates(self):
        from app.sources import ingest_real_dataset

        with tempfile.TemporaryDirectory() as tmp_dir:
            database_url = f"sqlite:///{tmp_dir}/amounts.db"
            engine = get_engine(database_url)
            ingest_real_dataset(
                raw_json=json.dumps(
                    [self.record("$1,001 - $15,000", 8000, ticker="PEP")]
                ),
                database_url=database_url,
            )
            # Así guardaba la versión anterior un tramo recortado.
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO trades (politician_id, ticker_id, trade_type, amount,"
                        " reported_date, transaction_date, notes)"
                        " SELECT politician_id, ticker_id, 'Sale', 15001, '2026-08-13',"
                        " '2026-07-17', 'x' FROM trades"
                    )
                )

            # La fuente sigue publicando el recorte: la pasada lo lee como
            # punto medio y encuentra la fila ya corregida.
            imported = ingest_real_dataset(
                raw_json=json.dumps([self.record("$15,001", 15001, ticker="PEP", day="13")]),
                database_url=database_url,
            )
            self.assertEqual(imported, [])

            with engine.connect() as connection:
                amounts = sorted(
                    row[0] for row in connection.execute(text("SELECT amount FROM trades"))
                )
            self.assertEqual(amounts, [8000.0, 32500.0])


if __name__ == "__main__":
    unittest.main()
