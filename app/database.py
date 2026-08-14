from collections.abc import Generator
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Politician, Ticker, Trade

DATABASE_URL = "sqlite:///./thewhalefiles.db"
_ENGINE_CACHE: dict[str, object] = {}


def get_engine(database_url: str = DATABASE_URL):
    if database_url not in _ENGINE_CACHE:
        engine_kwargs = {"connect_args": {"check_same_thread": False}}
        if database_url.startswith("sqlite://"):
            engine_kwargs["poolclass"] = StaticPool
        _ENGINE_CACHE[database_url] = create_engine(database_url, **engine_kwargs)
    return _ENGINE_CACHE[database_url]


engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from app.sources import ingest_real_dataset

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(Politician).first():
            return

        imported = ingest_real_dataset()
        if imported:
            return

        senator = Politician(
            name="Alex Morgan",
            chamber="Senate",
            state="California",
            party="Democratic",
        )
        rep = Politician(
            name="Jordan Lee",
            chamber="House",
            state="Texas",
            party="Republican",
        )

        apple = Ticker(symbol="AAPL", name="Apple Inc.")
        nvda = Ticker(symbol="NVDA", name="NVIDIA Corporation")
        msft = Ticker(symbol="MSFT", name="Microsoft Corporation")

        db.add_all([senator, rep, apple, nvda, msft])
        db.flush()

        trades = [
            Trade(
                politician_id=senator.id,
                ticker_id=apple.id,
                trade_type="Buy",
                amount=15000.0,
                reported_date=date(2026, 7, 12),
                notes="Compra reportada en el último filing del Senado.",
            ),
            Trade(
                politician_id=senator.id,
                ticker_id=nvda.id,
                trade_type="Buy",
                amount=25000.0,
                reported_date=date(2026, 7, 18),
                notes="Nueva posición en semiconductores.",
            ),
            Trade(
                politician_id=rep.id,
                ticker_id=msft.id,
                trade_type="Sell",
                amount=20000.0,
                reported_date=date(2026, 7, 28),
                notes="Venta parcial para reequilibrar cartera.",
            ),
        ]

        db.add_all(trades)
        db.commit()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
