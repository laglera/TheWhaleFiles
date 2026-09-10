"""Rehace las operaciones ya guardadas separando las dos fechas del filing.

Las primeras versiones guardaban en `reported_date` la fecha en que se ejecutó
la operación, pero la web la presenta —y la ordena— como fecha de publicación
del filing. Son cosas distintas: entre una y otra pueden pasar hasta 45 días,
que es justo la latencia que esta plataforma dice medir.

No se puede arreglar fila a fila con SQL, porque la fecha de publicación
sencillamente no estaba guardada: hay que volver a leer las fuentes. Por eso el
script borra lo importado y lo reingiere, en lugar de intentar deducirlo.

Uso:
    python -m scripts.repair_dates                # dataset del Congreso + SEC
    python -m scripts.repair_dates --skip-insiders  # sólo el Congreso
"""
from __future__ import annotations

import argparse
from datetime import date
from typing import Any

from sqlalchemy import func, select, text

from app.database import SessionLocal, prepare_database
from app.models import Trade
from app.sources import fetch_real_dataset, ingest_real_dataset

# Notas con las que se guardaron las operaciones del dataset público del
# Congreso. La primera es la nota por defecto de la ingesta, que durante un
# tiempo se aplicó también a los registros de la Cámara.
CONGRESS_NOTES = (
    "Imported from Senate filing",
    "Imported from House Stock Watcher dataset",
)


def _counts(db) -> dict[str, Any]:
    total = db.scalar(select(func.count(Trade.id))) or 0
    with_traded = db.scalar(
        select(func.count(Trade.id)).where(Trade.transaction_date.is_not(None))
    ) or 0
    newest = db.scalar(select(func.max(Trade.reported_date)))
    return {"trades": total, "con_fecha_de_operación": with_traded, "última_publicación": newest}


def repair_congress(db) -> int:
    """Borra lo importado del dataset del Congreso y lo vuelve a leer."""
    deleted = (
        db.query(Trade).filter(Trade.notes.in_(CONGRESS_NOTES)).delete(synchronize_session=False)
    )
    db.commit()
    return deleted or 0


def repair_insiders(db) -> int:
    """Borra los Form 4 guardados y sus posiciones, para releerlos de EDGAR.

    Las posiciones se recalculan solas al reimportar: `as_of` sale de la fecha
    de operación del Form 4 más reciente de cada valor.
    """
    deleted = db.execute(
        text("DELETE FROM trades WHERE notes LIKE 'SEC Form 4%'")
    ).rowcount
    db.execute(text("DELETE FROM holdings"))
    db.commit()
    return deleted or 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-insiders",
        action="store_true",
        help="No tocar las operaciones de la SEC (evita releer EDGAR, que tarda).",
    )
    args = parser.parse_args()

    prepare_database()

    # Se descarga antes de borrar nada: si la fuente no responde, la base se
    # queda como estaba en lugar de quedarse sin las operaciones del Congreso.
    raw_json = fetch_real_dataset()

    with SessionLocal() as db:
        print("Antes: ", _counts(db))
        borradas = repair_congress(db)
        print(f"Congreso: {borradas} operaciones borradas, reimportando...")

    importadas = ingest_real_dataset(raw_json=raw_json)
    print(f"Congreso: {len(importadas)} operaciones reimportadas con sus dos fechas")

    if not args.skip_insiders:
        from app.insiders import import_insiders

        with SessionLocal() as db:
            borradas = repair_insiders(db)
            print(f"SEC Form 4: {borradas} operaciones borradas, releyendo EDGAR...")
        resultado = import_insiders()
        print(
            f"SEC Form 4: {resultado['trades']} operaciones reimportadas, "
            f"{resultado['holdings']} posiciones recalculadas"
        )

    with SessionLocal() as db:
        print("Después:", _counts(db))
        futuras = db.scalar(
            select(func.count(Trade.id)).where(Trade.reported_date > date.today())
        )
        print(f"Operaciones con fecha de publicación futura: {futuras}")


if __name__ == "__main__":
    main()
