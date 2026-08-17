"""Copia la base local de SQLite a la de producción (Postgres).

La web sirve datos que se ingieren offline: en Vercel no hay proceso que pueda
rellenarla, así que los datos se preparan en local y se empujan desde aquí.

    python -m scripts.migrate_to_postgres --target "postgresql://..."

Sin --target se usa DATABASE_URL. Conserva los identificadores, porque las
fichas se enlazan por id (/politicians/278) y renumerarlas rompería los enlaces
que ya estén compartidos.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, inspect, select, text

from app.database import DEFAULT_DATABASE_URL, get_engine, prepare_database, resolve_database_url
from app.models import Holding, Politician, PriceQuote, Ticker, Trade

# El orden importa: las claves ajenas exigen que existan antes las personas y
# los valores a los que apuntan las operaciones.
MODELS = (Politician, Ticker, Trade, Holding, PriceQuote)
BATCH = 1000


def copy_table(source_engine, target_engine, model) -> int:
    table = model.__table__
    with source_engine.connect() as source:
        rows = [dict(row) for row in source.execute(select(table)).mappings()]

    if not rows:
        return 0

    with target_engine.begin() as target:
        for start in range(0, len(rows), BATCH):
            target.execute(table.insert(), rows[start : start + BATCH])
    return len(rows)


def reset_sequences(target_engine) -> None:
    """Pone los contadores de Postgres por encima del último id copiado.

    Los ids se insertan a mano, y la secuencia sigue en 1: sin esto, la primera
    fila que escribiera la app chocaría con una clave primaria ya usada.
    """
    if target_engine.dialect.name != "postgresql":
        return

    with target_engine.begin() as connection:
        for model in MODELS:
            name = model.__tablename__
            connection.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence(:table, 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {name}), 1))"
                ),
                {"table": name},
            )


def target_is_populated(target_engine) -> bool:
    inspector = inspect(target_engine)
    if Politician.__tablename__ not in inspector.get_table_names():
        return False
    with target_engine.connect() as connection:
        total = connection.execute(select(func.count()).select_from(Politician)).scalar_one()
    return bool(total)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=DEFAULT_DATABASE_URL, help="Base de origen")
    parser.add_argument("--target", default=None, help="Base de destino (por defecto DATABASE_URL)")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Vacía las tablas del destino antes de copiar",
    )
    args = parser.parse_args()

    target_url = resolve_database_url(args.target) if args.target else resolve_database_url()
    source_url = resolve_database_url(args.source)

    if target_url == source_url:
        print("El origen y el destino son la misma base. Indica --target.", file=sys.stderr)
        return 1

    source_engine = get_engine(source_url)
    target_engine = get_engine(target_url)

    print(f"Origen:  {source_url}")
    print(f"Destino: {target_url.split('@')[-1]}")

    prepare_database(target_engine)

    if target_is_populated(target_engine):
        if not args.replace:
            print(
                "El destino ya tiene datos. Usa --replace para sobrescribirlo.",
                file=sys.stderr,
            )
            return 1
        with target_engine.begin() as connection:
            for model in reversed(MODELS):
                connection.execute(model.__table__.delete())
        print("Destino vaciado.")

    total = 0
    for model in MODELS:
        copied = copy_table(source_engine, target_engine, model)
        total += copied
        print(f"  {model.__tablename__}: {copied:,} filas")

    reset_sequences(target_engine)
    print(f"Listo: {total:,} filas copiadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
