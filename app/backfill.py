"""Reparaciones sobre datos ya almacenados por versiones anteriores.

Las primeras ingestas creaban a todos los congresistas con los valores por
defecto del parser del Senado, así que los 300 representantes de la Cámara
quedaron guardados como "Senate / California", y con el nombre tal cual lo
escribe la fuente, variantes incluidas.

Es de un solo uso por base: una vez corregida, la ingesta ya guarda bien
cámara, estado y nombre.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import select, text

from app.database import SessionLocal, prepare_database
from app.models import Politician
from app.names import clean_person_name
from app.sources import REAL_DATASET_URL, fetch_real_dataset


def merge_duplicate_politicians(db) -> dict[str, int]:
    """Unifica las fichas que son la misma persona escrita de otra forma.

    Se opera con SQL explícito: al borrar una ficha por el ORM, la relación
    `trades` desasocia sus operaciones poniéndoles `politician_id` a nulo en
    lugar de dejarlas en la ficha buena.
    """
    stats = {"renamed": 0, "merged": 0, "trades_moved": 0, "trades_dropped": 0}

    rows = db.execute(
        select(Politician.id, Politician.name)
        .where(Politician.category == "congress")
        .order_by(Politician.id)
    ).all()

    canonical: dict[str, int] = {}
    for person_id, raw_name in rows:
        clean = clean_person_name(raw_name)
        keeper_id = canonical.get(clean)

        if keeper_id is None:
            canonical[clean] = person_id
            if raw_name != clean:
                db.execute(
                    text("UPDATE politicians SET name = :name WHERE id = :id"),
                    {"name": clean, "id": person_id},
                )
                stats["renamed"] += 1
            continue

        # La misma operación puede constar en las dos fichas: moverla chocaría
        # contra el índice de unicidad, así que primero se descarta la copia.
        dropped = db.execute(
            text(
                "DELETE FROM trades WHERE politician_id = :dup AND EXISTS ("
                " SELECT 1 FROM trades keep WHERE keep.politician_id = :keeper"
                " AND keep.ticker_id = trades.ticker_id"
                " AND keep.trade_type = trades.trade_type"
                " AND keep.amount = trades.amount"
                " AND keep.reported_date = trades.reported_date)"
            ),
            {"dup": person_id, "keeper": keeper_id},
        )
        moved = db.execute(
            text("UPDATE trades SET politician_id = :keeper WHERE politician_id = :dup"),
            {"dup": person_id, "keeper": keeper_id},
        )
        db.execute(text("DELETE FROM politicians WHERE id = :id"), {"id": person_id})

        stats["trades_dropped"] += dropped.rowcount or 0
        stats["trades_moved"] += moved.rowcount or 0
        stats["merged"] += 1

    db.commit()
    db.expire_all()
    return stats


def refresh_congress_metadata(db, dataset: list[dict[str, Any]]) -> dict[str, int]:
    """Corrige cámara y estado de los congresistas a partir del district."""
    states: dict[str, str] = {}
    for item in dataset:
        name = clean_person_name(str(item.get("representative") or ""))
        district = str(item.get("district") or "").strip().upper()
        if name and len(district) >= 2 and district[:2].isalpha():
            states[name] = district[:2]

    stats = {"updated": 0, "unknown": 0}
    for person in db.scalars(
        select(Politician).where(Politician.category == "congress")
    ).all():
        state = states.get(person.name)
        if not state:
            stats["unknown"] += 1
            continue
        if person.chamber != "House" or person.state != state:
            person.chamber = "House"
            person.state = state
            stats["updated"] += 1

    db.commit()
    return stats


def run(raw_json: Optional[str] = None) -> dict[str, Any]:
    prepare_database()
    dataset = json.loads(raw_json if raw_json is not None else fetch_real_dataset(REAL_DATASET_URL))
    with SessionLocal() as db:
        merged = merge_duplicate_politicians(db)
        refreshed = refresh_congress_metadata(db, dataset)
    return {"merge": merged, "metadata": refreshed}


if __name__ == "__main__":
    print("Reparando fichas de congresistas...")
    print(run())
