"""Base de datos de usar y tirar para las pruebas que necesitan contenido.

Las páginas públicas se comprobaban contra la base del directorio de trabajo y
daban por hecho que alguien había ingerido datos antes. En un portátil con el
dataset descargado pasaban; en el runner, donde la base nace vacía, reventaban
al pedirle "el primer político" y recibir None. Cada prueba se monta aquí los
datos que necesita, así que el resultado no depende de qué haya en el disco.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Politician, Ticker, Trade


def memory_session() -> Session:
    """Sesión sobre un SQLite en memoria con el esquema ya creado."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def seed_declarant(db: Session, name: str = "Alex Morgan", trades: int = 6) -> Politician:
    """Una persona con operaciones declaradas, como las que pinta la web.

    Los importes y las fechas cambian en cada una porque la identidad de una
    operación incluye ambos: repetirlos haría que la segunda chocara contra
    `uq_trade_identity` en vez de guardarse.
    """
    person = Politician(name=name, chamber="House", state="WA", party="Democrat")
    db.add(person)
    db.flush()

    ticker = Ticker(symbol="ACME", name="Acme Corp")
    db.add(ticker)
    db.flush()

    published = date(2026, 3, 1)
    for index in range(trades):
        db.add(
            Trade(
                politician_id=person.id,
                ticker_id=ticker.id,
                trade_type="Purchase" if index % 2 == 0 else "Sale",
                amount=1000.0 * (index + 1),
                reported_date=published + timedelta(days=index),
                transaction_date=published + timedelta(days=index - 10),
            )
        )
    db.flush()
    return person
