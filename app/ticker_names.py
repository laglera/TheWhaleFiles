"""Nombre de la empresa detrás de cada símbolo.

La ingesta crea cada valor con el símbolo como nombre, porque ni el PTR del
Congreso ni la línea del Form 4 traen otro: el historial enseñaba "PG" o
"MBLY" sin decir de qué empresa se trataba. La SEC publica en un solo fichero
el símbolo y la razón social de todo lo que cotiza en EEUU, así que una
petición basta para todos. Lo que ya no cotiza —buena parte del histórico del
Congreso desde 2016— se queda con el símbolo.

Fuente: EDGAR (dominio público).
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy import or_, select

from app.database import SessionLocal, prepare_database
from app.insiders import _fetch
from app.models import Ticker

logger = logging.getLogger(__name__)

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def symbol_key(symbol: str) -> str:
    """Las clases de acción van con punto en la base y con guion en la SEC."""
    return (symbol or "").strip().upper().replace(".", "-").replace("/", "-")


def parse_sec_tickers(payload: dict) -> dict[str, str]:
    names: dict[str, str] = {}
    for entry in (payload or {}).values():
        symbol = symbol_key(str(entry.get("ticker") or ""))
        title = str(entry.get("title") or "").strip()
        # El fichero lista primero la clase principal: no se pisa con otras.
        if symbol and title and symbol not in names:
            names[symbol] = title
    return names


def fetch_sec_names() -> Optional[dict[str, str]]:
    try:
        return parse_sec_tickers(json.loads(_fetch(SEC_TICKERS_URL)))
    except (OSError, ValueError):
        logger.exception("No se pudo descargar la lista de valores de la SEC")
        return None


def fill_ticker_names(names: Optional[dict[str, str]] = None, verbose: bool = True) -> dict[str, int]:
    """Pone nombre a los valores que sólo tienen el símbolo."""
    prepare_database()
    stats = {"missing": 0, "named": 0}
    names = fetch_sec_names() if names is None else names
    if not names:
        return stats
    with SessionLocal() as db:
        pending = db.scalars(
            select(Ticker).where(or_(Ticker.name == Ticker.symbol, Ticker.name == ""))
        ).all()
        stats["missing"] = len(pending)
        for ticker in pending:
            name = names.get(symbol_key(ticker.symbol))
            if name:
                ticker.name = name[:255]
                stats["named"] += 1
        db.commit()
    if verbose:
        print(f"Valores con nombre nuevo: {stats['named']} de {stats['missing']} sin nombre")
    return stats


if __name__ == "__main__":
    fill_ticker_names()
