from collections.abc import Generator
from datetime import date

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Politician, Ticker, Trade

DATABASE_URL = "sqlite:///./thewhalefiles.db"
_ENGINE_CACHE: dict[str, object] = {}


def get_engine(database_url: str = DATABASE_URL):
    if database_url in _ENGINE_CACHE:
        return _ENGINE_CACHE[database_url]

    is_sqlite = database_url.startswith("sqlite://")
    is_memory = ":memory:" in database_url

    engine_kwargs: dict[str, object] = {}
    if is_sqlite:
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        # StaticPool solo sirve para bases en memoria, donde cada conexión nueva
        # sería una base distinta. Sobre un fichero compartiría una única
        # conexión entre hilos, y el hilo de polling escribiendo a la vez que
        # una petición web lee corrompe el estado del módulo sqlite3.
        if is_memory:
            engine_kwargs["poolclass"] = StaticPool

    engine = create_engine(database_url, **engine_kwargs)

    if is_sqlite and not is_memory:

        @event.listens_for(engine, "connect")
        def _configure_sqlite(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            # WAL permite lecturas concurrentes con una escritura en curso.
            cursor.execute("PRAGMA journal_mode=WAL")
            # Sin esto, el hilo de polling da "database is locked" al instante.
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    _ENGINE_CACHE[database_url] = engine
    return engine


engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


TRADE_IDENTITY_COLUMNS = "politician_id, ticker_id, trade_type, amount, reported_date"


def ensure_schema(target_engine=None) -> None:
    """Migraciones mínimas para bases creadas por versiones anteriores.

    `create_all` no toca tablas que ya existen, así que las bases anteriores
    necesitan tanto la columna `category` como el índice de unicidad de trades.
    """
    from sqlalchemy import inspect, text

    target_engine = target_engine or engine
    inspector = inspect(target_engine)
    table_names = set(inspector.get_table_names())

    if "politicians" in table_names:
        columns = {column["name"] for column in inspector.get_columns("politicians")}
        if "category" not in columns:
            with target_engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE politicians "
                        "ADD COLUMN category VARCHAR(20) NOT NULL DEFAULT 'congress'"
                    )
                )

    if "trades" in table_names:
        existing = {index["name"] for index in inspector.get_indexes("trades")}
        existing |= {
            constraint["name"] for constraint in inspector.get_unique_constraints("trades")
        }
        if "uq_trade_identity" not in existing:
            with target_engine.begin() as connection:
                # Las bases anteriores acumularon una copia de cada operación por
                # cada pasada de ingesta; hay que limpiarlas antes de que el
                # índice pueda aplicarse.
                connection.execute(
                    text(
                        "DELETE FROM trades WHERE id NOT IN ("
                        f"SELECT MIN(id) FROM trades GROUP BY {TRADE_IDENTITY_COLUMNS}"
                        ")"
                    )
                )
                connection.execute(
                    text(
                        "CREATE UNIQUE INDEX uq_trade_identity "
                        f"ON trades ({TRADE_IDENTITY_COLUMNS})"
                    )
                )


def init_db() -> None:
    from app.sources import ingest_real_dataset

    Base.metadata.create_all(bind=engine)
    ensure_schema()
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
