"""Pruebas del resumen que se pinta en cada ficha de la portada.

Es lo que responde "¿en qué invierte esta persona?" sin abrir su perfil, así
que lo que se comprueba aquí es que las tres cifras que lo componen —dónde está
concentrado el dinero, el sesgo comprador y la última operación— salen de los
datos declarados y no de un orden accidental.
"""

import unittest
from datetime import date

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import DIGEST_POSITIONS, attach_digests
from app.models import Base, Politician, Ticker, Trade


class DigestTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()

        self.person = Politician(
            name="Alex Morgan", chamber="House", state="WA", party="Unknown"
        )
        self.db.add(self.person)
        self.db.flush()

    def tearDown(self):
        self.db.close()

    def add_trade(self, symbol, trade_type, amount, reported_date):
        ticker = self.db.scalar(select(Ticker).where(Ticker.symbol == symbol))
        if not ticker:
            ticker = Ticker(symbol=symbol, name=symbol)
            self.db.add(ticker)
            self.db.flush()
        self.db.add(
            Trade(
                politician_id=self.person.id,
                ticker_id=ticker.id,
                trade_type=trade_type,
                amount=amount,
                reported_date=reported_date,
            )
        )
        self.db.flush()

    def digest(self):
        """El resumen de la persona, con el mismo filtro que usa la portada."""
        scoped_ids = (
            select(Trade).join(Trade.politician).join(Trade.ticker)
        ).with_only_columns(Trade.id).subquery()
        volume = self.db.scalar(
            select(func.coalesce(func.sum(Trade.amount), 0.0)).where(
                Trade.politician_id == self.person.id
            )
        )
        operations = self.db.scalar(
            select(func.count(Trade.id)).where(Trade.politician_id == self.person.id)
        )
        people = [
            {
                "id": self.person.id,
                "name": self.person.name,
                "operations": operations,
                "volume": float(volume),
            }
        ]
        attach_digests(self.db, people, scoped_ids)
        return people[0]

    def test_positions_are_ranked_by_capital_and_capped(self):
        # Seis valores para que el corte tenga algo que cortar, y el más
        # operado no es el que más dinero mueve: si el orden fuera por número
        # de operaciones, RARE quedaría por encima de BIG.
        self.add_trade("BIG", "Purchase", 500_000, date(2026, 1, 1))
        for day in range(1, 5):
            self.add_trade("RARE", "Purchase", 1_000, date(2026, 1, day))
        for symbol, amount in [("C", 300), ("D", 200), ("E", 100), ("F", 50)]:
            self.add_trade(symbol, "Purchase", amount, date(2026, 1, 1))

        positions = self.digest()["positions"]
        self.assertEqual(len(positions), DIGEST_POSITIONS)
        self.assertEqual([entry["symbol"] for entry in positions], ["BIG", "RARE", "C", "D"])

    def test_the_share_is_measured_against_the_declared_capital(self):
        self.add_trade("AAA", "Purchase", 750_000, date(2026, 1, 1))
        self.add_trade("BBB", "Purchase", 250_000, date(2026, 1, 1))

        positions = self.digest()["positions"]
        self.assertEqual(positions[0]["share"], 75.0)
        self.assertEqual(positions[1]["share"], 25.0)

    def test_uncounted_positions_are_reported_not_hidden(self):
        for index in range(DIGEST_POSITIONS + 3):
            self.add_trade(f"T{index}", "Purchase", 1_000 - index, date(2026, 1, 1))

        self.assertEqual(self.digest()["other_positions"], 3)

    def test_the_bias_leaves_unclassified_trades_out_of_the_denominator(self):
        # Los Formulario 4 traen códigos que no son ni compra ni venta (premios,
        # ejercicios de opciones): meterlos en el reparto diluiría el sesgo.
        self.add_trade("AAA", "Purchase", 100, date(2026, 1, 1))
        self.add_trade("AAA", "Purchase", 100, date(2026, 1, 2))
        self.add_trade("AAA", "Purchase", 100, date(2026, 1, 3))
        self.add_trade("AAA", "Sale", 100, date(2026, 1, 4))
        self.add_trade("AAA", "Award", 100, date(2026, 1, 5))

        digest = self.digest()
        self.assertEqual(digest["buy_share"], 75)
        self.assertEqual(digest["sides"], {"buy": 3, "sell": 1, "other": 1})

    def test_someone_with_no_classified_trades_has_no_bias(self):
        self.add_trade("AAA", "Award", 100, date(2026, 1, 1))

        # None, no cero: no es que no compre, es que no se puede saber.
        self.assertIsNone(self.digest()["buy_share"])

    def test_the_latest_trade_is_the_most_recently_reported_one(self):
        self.add_trade("OLD", "Purchase", 100, date(2025, 5, 1))
        self.add_trade("NEW", "Sale", 100, date(2026, 3, 2))
        self.add_trade("MID", "Purchase", 100, date(2026, 1, 9))

        last = self.digest()["last_trade"]
        self.assertEqual(last["symbol"], "NEW")
        self.assertEqual(last["trade_type"], "Sale")
        self.assertEqual(last["date"], date(2026, 3, 2))

    def test_a_person_without_trades_gets_an_empty_digest(self):
        digest = self.digest()
        self.assertEqual(digest["positions"], [])
        self.assertIsNone(digest["last_trade"])
        self.assertIsNone(digest["buy_share"])

    def test_an_empty_page_does_not_query_anything(self):
        scoped_ids = (
            select(Trade).join(Trade.politician).join(Trade.ticker)
        ).with_only_columns(Trade.id).subquery()
        # Sin personas visibles no hay nada que resumir, y el `IN ()` de la
        # consulta no llega a construirse.
        attach_digests(self.db, [], scoped_ids)


if __name__ == "__main__":
    unittest.main()
