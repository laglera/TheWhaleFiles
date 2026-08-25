import tempfile
import unittest
from pathlib import Path

from sqlalchemy import inspect, text

from app.database import get_engine, prepare_database


# Esquema tal y como lo dejaron las versiones anteriores: sin la fecha de
# operación, y con la identidad de unicidad construida sobre cinco columnas.
LEGACY_SCHEMA = """
CREATE TABLE politicians (
    id INTEGER NOT NULL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    chamber VARCHAR(80) NOT NULL,
    state VARCHAR(80) NOT NULL,
    party VARCHAR(60) NOT NULL
);
CREATE TABLE tickers (
    id INTEGER NOT NULL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL
);
CREATE TABLE trades (
    id INTEGER NOT NULL PRIMARY KEY,
    politician_id INTEGER NOT NULL,
    ticker_id INTEGER NOT NULL,
    trade_type VARCHAR(30) NOT NULL,
    amount FLOAT NOT NULL,
    reported_date DATE NOT NULL,
    notes VARCHAR(500) NOT NULL
);
CREATE UNIQUE INDEX uq_trade_identity
    ON trades (politician_id, ticker_id, trade_type, amount, reported_date);
"""


class LegacySchemaMigrationTests(unittest.TestCase):
    """Una base de una versión anterior tiene que poder abrirse sin perder nada.

    Es lo que hace el despliegue al arrancar: no hay paso manual de migración,
    así que `prepare_database` es lo único que separa el esquema viejo del
    nuevo.
    """

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        path = Path(self.tmp_dir.name) / "legacy.db"
        self.engine = get_engine(f"sqlite:///{path}")

        with self.engine.begin() as conn:
            for statement in LEGACY_SCHEMA.strip().split(";"):
                if statement.strip():
                    conn.execute(text(statement))
            conn.execute(
                text("INSERT INTO politicians VALUES (1, 'Mike Kelly', 'House', 'PA', '')")
            )
            conn.execute(text("INSERT INTO tickers VALUES (1, 'ABT', 'Abbott')"))
            conn.execute(
                text(
                    "INSERT INTO trades VALUES (1, 1, 1, 'Sale', 8000.0, '2026-08-12', 'nota')"
                )
            )

    def test_the_new_column_appears_without_touching_the_rows(self):
        prepare_database(self.engine)

        with self.engine.begin() as conn:
            rows = conn.execute(
                text("SELECT reported_date, transaction_date FROM trades")
            ).all()

        # La fecha de publicación que ya estaba se respeta; la de operación
        # nace vacía porque en esa base nunca se guardó.
        self.assertEqual(rows, [("2026-08-12", None)])

    def test_the_identity_index_is_rebuilt_with_both_dates(self):
        prepare_database(self.engine)

        indexes = {
            index["name"]: list(index["column_names"])
            for index in inspect(self.engine).get_indexes("trades")
        }

        self.assertEqual(
            indexes["uq_trade_identity"],
            [
                "politician_id",
                "ticker_id",
                "trade_type",
                "amount",
                "reported_date",
                "transaction_date",
            ],
        )

    def test_migrating_twice_changes_nothing(self):
        prepare_database(self.engine)
        prepare_database(self.engine)

        with self.engine.begin() as conn:
            self.assertEqual(
                conn.execute(text("SELECT COUNT(*) FROM trades")).scalar(), 1
            )


if __name__ == "__main__":
    unittest.main()
