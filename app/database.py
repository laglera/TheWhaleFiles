from __future__ import annotations

import os
from collections.abc import Generator
from datetime import date

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.models import Base, Politician, Ticker, Trade

DEFAULT_DATABASE_URL = "sqlite:///./thewhalefiles.db"

# Cuando la base se crea desde el panel de Vercel, la integración inyecta ella
# misma las credenciales, y no siempre con el nombre DATABASE_URL. Se aceptan
# los alias habituales para no tener que duplicar la variable a mano.
DATABASE_URL_VARS = ("DATABASE_URL", "POSTGRES_URL", "POSTGRES_URL_NON_POOLING")


def resolve_database_url(raw: str | None = None) -> str:
    """URL de la base, con SQLite local como valor por defecto.

    Fuera del ordenador de casa no hay disco donde escribir —en una función
    serverless el sistema de archivos es de sólo lectura—, así que el destino
    se indica por entorno y apunta a un Postgres gestionado.
    """
    if raw is not None:
        url = raw
    else:
        url = next(
            (value for var in DATABASE_URL_VARS if (value := os.getenv(var))),
            DEFAULT_DATABASE_URL,
        )

    # Varios proveedores siguen entregando el esquema "postgres://", que
    # SQLAlchemy 2 ya no reconoce.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


DATABASE_URL = resolve_database_url()
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
    else:
        # Sin pool: la función serverless muere al responder y dejaría las
        # conexiones abiertas del lado del servidor hasta agotar su límite.
        # pool_pre_ping descarta las que el proveedor haya cerrado por su cuenta.
        engine_kwargs["poolclass"] = NullPool
        engine_kwargs["pool_pre_ping"] = True

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

# Columnas añadidas después de las primeras versiones de la base. `create_all`
# no toca tablas existentes, así que hay que añadirlas a mano.
ADDED_COLUMNS = {
    "politicians": [
        ("category", "VARCHAR(20) NOT NULL DEFAULT 'congress'"),
        ("bio_es", "TEXT"),
        ("bio_en", "TEXT"),
        ("bio_headline_es", "VARCHAR(255)"),
        ("bio_headline_en", "VARCHAR(255)"),
        ("bio_source_url", "VARCHAR(500)"),
        ("photo_remote_url", "VARCHAR(500)"),
        ("photo_author", "VARCHAR(255)"),
        ("photo_license", "VARCHAR(120)"),
        ("photo_source_url", "VARCHAR(500)"),
        ("profile_fetched_at", "DATETIME"),
    ],
}


def ensure_schema(target_engine=None) -> None:
    """Migraciones mínimas para bases creadas por versiones anteriores."""
    from sqlalchemy import inspect, text

    target_engine = target_engine or engine
    inspector = inspect(target_engine)
    table_names = set(inspector.get_table_names())

    for table, columns in ADDED_COLUMNS.items():
        if table not in table_names:
            continue
        existing = {column["name"] for column in inspector.get_columns(table)}
        missing = [(name, ddl) for name, ddl in columns if name not in existing]
        if missing:
            with target_engine.begin() as connection:
                for name, ddl in missing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))

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


def prepare_database(target_engine=None) -> None:
    """Crea lo que falte y migra lo que exista. Todo punto de entrada la llama."""
    target_engine = target_engine or engine
    Base.metadata.create_all(bind=target_engine)
    ensure_schema(target_engine)


def init_db() -> None:
    from app.sources import ingest_real_dataset

    prepare_database()
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
