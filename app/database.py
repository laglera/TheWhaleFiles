from __future__ import annotations

import logging
import os
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.models import Base, Politician

LOGGER = logging.getLogger(__name__)

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

    # Un salto de línea al final es lo más fácil del mundo cuando la cadena se
    # copia de un fichero a un gestor de secretos con una tubería: viaja pegado
    # al valor, acaba dentro del nombre del host y la conexión falla con un
    # error que no señala a ninguna parte.
    url = url.strip()

    # Los paneles de Neon y compañía ofrecen la cadena lista para la consola
    # —`psql 'postgresql://…'`— y es fácil copiarla entera, o la línea del
    # .env con su `DATABASE_URL=` delante. SQLAlchemy no reconoce ninguna de
    # las dos y el error no enseña el valor, porque es un secreto.
    if url.lower().startswith("psql "):
        url = url[5:].strip()
    for var in DATABASE_URL_VARS:
        if url.startswith(f"{var}="):
            url = url[len(var) + 1 :].strip()
    if len(url) >= 2 and url[0] == url[-1] and url[0] in "'\"":
        url = url[1:-1].strip()

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


TRADE_IDENTITY_COLUMNS = (
    "politician_id, ticker_id, trade_type, amount, reported_date, transaction_date"
)
# La identidad de las primeras versiones, sin la fecha de operación. Se guarda
# para poder retirar el índice viejo al migrar.
LEGACY_TRADE_IDENTITY_COLUMNS = "politician_id, ticker_id, trade_type, amount, reported_date"

# Columnas añadidas después de las primeras versiones de la base. `create_all`
# no toca tablas existentes, así que hay que añadirlas a mano.
ADDED_COLUMNS = {
    "trades": [
        ("transaction_date", "DATE"),
    ],
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


# Columnas que nacieron como coma flotante y ahora son NUMERIC (app/money.py).
# Sólo cambian en Postgres: SQLite no tiene tipo decimal y allí siguen siendo
# REAL, redondeadas a su escala al leer y al escribir.
NUMERIC_COLUMNS = {
    "trades": [("amount", "NUMERIC(19,4)")],
    "holdings": [("shares", "NUMERIC(24,6)")],
    "price_quotes": [("price", "NUMERIC(19,6)"), ("previous_close", "NUMERIC(19,6)")],
}


def numeric_migrations(inspector, dialect_name: str) -> list[str]:
    """ALTER TABLE que faltan para pasar las columnas de dinero a NUMERIC."""
    from sqlalchemy.types import Float, Numeric

    if dialect_name != "postgresql":
        return []
    table_names = set(inspector.get_table_names())
    statements = []
    for table, columns in NUMERIC_COLUMNS.items():
        if table not in table_names:
            continue
        current = {column["name"]: column["type"] for column in inspector.get_columns(table)}
        for name, ddl in columns:
            column_type = current.get(name)
            # Float hereda de Numeric en SQLAlchemy: hay que descartarlo aparte.
            if column_type is None or (
                isinstance(column_type, Numeric) and not isinstance(column_type, Float)
            ):
                continue
            statements.append(
                f"ALTER TABLE {table} ALTER COLUMN {name} TYPE {ddl} USING {name}::{ddl}"
            )
    return statements


def _identity_of(inspector, table: str, name: str) -> list[str] | None:
    """Columnas que indexa una restricción de unicidad, esté como esté creada."""
    for constraint in inspector.get_unique_constraints(table):
        if constraint["name"] == name:
            return list(constraint["column_names"])
    for index in inspector.get_indexes(table):
        if index["name"] == name:
            return list(index["column_names"])
    return None


def ensure_schema(target_engine=None) -> None:
    """Migraciones mínimas para bases creadas por versiones anteriores."""
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import SQLAlchemyError

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

    statements = numeric_migrations(inspector, target_engine.dialect.name)
    if statements:
        # Si falla —una fila que al redondear chocara con otra en el índice de
        # unicidad, por ejemplo— la web sigue sirviendo con las columnas
        # viejas: todo el código convierte a Decimal al leer. Mejor eso que
        # tumbar cada petición en el arranque.
        try:
            with target_engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))
            LOGGER.info("Columnas de importes migradas a NUMERIC: %s", len(statements))
        except SQLAlchemyError:
            LOGGER.exception("No se pudieron migrar las columnas de importes a NUMERIC")

    if "trades" in table_names:
        # `get_indexes` no ve las restricciones UNIQUE declaradas en el CREATE
        # TABLE, y `get_unique_constraints` no ve los índices creados aquí a
        # mano: `_identity_of` mira en los dos sitios.
        constraint_names = {
            constraint["name"] for constraint in inspector.get_unique_constraints("trades")
        }

        identity_columns = _identity_of(inspector, "trades", "uq_trade_identity")
        expected = [column.strip() for column in TRADE_IDENTITY_COLUMNS.split(",")]

        # El índice viejo indexaba sin la fecha de operación: dos operaciones
        # declaradas el mismo día en el mismo filing chocaban entre sí y la
        # segunda se perdía. Se sustituye por el que incluye las dos fechas.
        if identity_columns is not None and identity_columns != expected:
            with target_engine.begin() as connection:
                if "uq_trade_identity" in constraint_names:
                    connection.execute(
                        text("ALTER TABLE trades DROP CONSTRAINT uq_trade_identity")
                    )
                else:
                    connection.execute(text("DROP INDEX uq_trade_identity"))
            identity_columns = None

        if identity_columns is None:
            with target_engine.begin() as connection:
                # Las bases anteriores acumularon una copia de cada operación por
                # cada pasada de ingesta; hay que limpiarlas antes de que el
                # índice pueda aplicarse.
                connection.execute(
                    text(
                        "DELETE FROM trades WHERE id NOT IN ("
                        f"SELECT MIN(id) FROM trades GROUP BY {LEGACY_TRADE_IDENTITY_COLUMNS}"
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


def seed_from_network() -> bool:
    """Si la primera siembra puede descargar el dataset público.

    En integración continua no: la base nace vacía en cada ejecución y bajar
    veinticinco mil operaciones para correr las pruebas es lento y depende de
    que GitHub conteste. Las pruebas se montan sus propios datos.
    """
    return os.getenv("SEED_REAL_DATASET", "1").lower() not in {"0", "false", "no"}


def init_db() -> None:
    """Siembra la base la primera vez, sólo con operaciones declaradas de verdad.

    Antes, si la descarga fallaba, se caía en unos registros de ejemplo con dos
    políticos inventados. Servía para ver la web llena en local, pero en un
    despliegue con la red torcida esos nombres se publicaban con el mismo
    aspecto que los reales. Una base vacía se explica sola; una base con datos
    falsos, no.
    """
    from app.sources import ingest_real_dataset

    prepare_database()
    with SessionLocal() as db:
        if db.query(Politician).first():
            return

    if not seed_from_network():
        return

    if not ingest_real_dataset():
        LOGGER.error(
            "La siembra inicial no importó ninguna operación: la base queda vacía "
            "hasta que la fuente vuelva a estar disponible."
        )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
