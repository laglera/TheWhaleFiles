"""Histórico de cotizaciones, splits y dividendos.

Dos cosas dependen de él. La valoración: una posición declarada antes de un
split tiene que contarse con los títulos de después, y los dividendos cobrados
desde la fecha del saldo son patrimonio aunque el Form 4 no los diga. Y la
rentabilidad de copiar a cada persona (app/performance.py), que necesita el
cierre de cada sesión de cada valor que opera y del índice de referencia.

Todo sale de una sola llamada por valor al endpoint `chart` de Yahoo, que
devuelve los cierres ajustados y los eventos del periodo. Yahoo limita por
ráfaga, así que cada pasada refresca un número acotado de valores
(`HISTORY_MAX_SYMBOLS`), empezando por los que no tienen datos y siguiendo por
los más viejos: el universo entero se renueva en unas pocas pasadas.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable, Optional

from sqlalchemy import func, or_, select

from app.database import SessionLocal, prepare_database
from app.models import CorporateAction, DerivativeHolding, Holding, PriceHistory, Ticker, Trade
from app.money import PRICE_SCALE, to_decimal
from app.prices import normalise_currency, yahoo_chart
from app.runtime import utcnow

logger = logging.getLogger(__name__)

# Años de operaciones que entran en el cálculo de rentabilidad, y de sesiones
# que se guardan (uno más, para poder seguir las últimas posiciones abiertas).
HISTORY_YEARS = int(os.getenv("HISTORY_YEARS", "3"))
# Valores que se piden a Yahoo por pasada. Con la pausa entre peticiones, unos
# 300 caben holgados en el refresco de cada seis horas.
MAX_SYMBOLS_PER_RUN = int(os.getenv("HISTORY_MAX_SYMBOLS", "300"))
# Índice con el que se compara todo: el S&P 500 a través de su ETF, que sí
# reparte dividendos y tiene cierre ajustado como cualquier acción.
BENCHMARK = os.getenv("BENCHMARK_SYMBOL", "SPY").strip().upper()
# Un histórico se da por al día si se pidió hace menos de esto.
REFRESH_AFTER = timedelta(hours=20)

OPEN_MARKET_TYPES = ("purchase", "buy", "sale", "sell")


# --- Lectura de Yahoo ------------------------------------------------------


def parse_chart(payload: Optional[dict]) -> Optional[dict[str, Any]]:
    """Cierres ajustados, splits y dividendos de una respuesta de `chart`."""
    results = ((payload or {}).get("chart") or {}).get("result") or []
    if not results:
        return None
    result = results[0]
    meta = result.get("meta") or {}
    currency, divisor = normalise_currency(meta.get("currency"))
    # Las fechas llegan como instante UTC de la apertura; con el desfase de la
    # bolsa se recupera el día de la sesión, que es el que importa.
    offset = timedelta(seconds=int(meta.get("gmtoffset") or 0))

    def session_day(timestamp: Any) -> date:
        return (datetime.fromtimestamp(int(timestamp), tz=timezone.utc) + offset).date()

    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators") or {}
    adjusted = ((indicators.get("adjclose") or [{}])[0] or {}).get("adjclose") or []
    raw = ((indicators.get("quote") or [{}])[0] or {}).get("close") or []
    series = adjusted if any(value is not None for value in adjusted) else raw

    bars: dict[date, Decimal] = {}
    for timestamp, value in zip(timestamps, series):
        close = to_decimal(value)
        if close is None or close <= 0:
            continue
        bars[session_day(timestamp)] = (close / divisor).quantize(Decimal(1).scaleb(-PRICE_SCALE))

    events = result.get("events") or {}
    splits = []
    for event in (events.get("splits") or {}).values():
        numerator = to_decimal(event.get("numerator"))
        denominator = to_decimal(event.get("denominator"))
        if numerator and denominator:
            splits.append((session_day(event.get("date")), numerator / denominator))
    dividends = []
    for event in (events.get("dividends") or {}).values():
        amount = to_decimal(event.get("amount"))
        if amount:
            dividends.append((session_day(event.get("date")), amount / divisor))

    return {
        "currency": currency,
        "bars": sorted(bars.items()),
        "splits": sorted(splits),
        "dividends": sorted(dividends),
    }


def fetch_history(symbol: str, years: int) -> Optional[dict[str, Any]]:
    # `range` sólo admite unos pocos valores; 5y cubre el periodo por defecto.
    span = "5y" if years <= 4 else "10y"
    return parse_chart(
        yahoo_chart(symbol, f"interval=1d&range={span}&events=div%2Csplit&includeAdjustedClose=true")
    )


# --- Almacén ---------------------------------------------------------------


def encode_closes(bars: Iterable[tuple[date, Decimal]]) -> str:
    bars = list(bars)
    return json.dumps(
        {"d": [day.isoformat() for day, _ in bars], "c": [str(close) for _, close in bars]},
        separators=(",", ":"),
    )


def decode_closes(text: str) -> list[tuple[date, Decimal]]:
    if not text:
        return []
    data = json.loads(text)
    return [
        (date.fromisoformat(day), Decimal(close))
        for day, close in zip(data.get("d", []), data.get("c", []))
    ]


def load_series(db, symbols: Iterable[str]) -> dict[str, list[tuple[date, Decimal]]]:
    """Cierres ajustados por valor, ordenados por día."""
    wanted = sorted({symbol for symbol in symbols if symbol})
    if not wanted:
        return {}
    rows = db.scalars(select(PriceHistory).where(PriceHistory.symbol.in_(wanted))).all()
    return {row.symbol: decode_closes(row.closes) for row in rows if row.closes}


def load_actions(db, symbols: Iterable[str]) -> dict[str, list[CorporateAction]]:
    wanted = sorted({symbol for symbol in symbols if symbol})
    actions: dict[str, list[CorporateAction]] = {}
    if not wanted:
        return actions
    for action in db.scalars(
        select(CorporateAction)
        .where(CorporateAction.symbol.in_(wanted))
        .order_by(CorporateAction.day)
    ).all():
        actions.setdefault(action.symbol, []).append(action)
    return actions


def store_history(db, symbol: str, parsed: Optional[dict[str, Any]], now: datetime) -> int:
    """Guarda lo descargado. Devuelve cuántas sesiones quedan guardadas."""
    row = db.scalar(select(PriceHistory).where(PriceHistory.symbol == symbol))
    if row is None:
        row = PriceHistory(symbol=symbol, closes="")
        db.add(row)
    row.fetched_at = now
    if not parsed or not parsed["bars"]:
        return len(decode_closes(row.closes))

    # Lo descargado sustituye a lo guardado entero: los cierres ajustados de
    # todo el pasado cambian con cada dividendo nuevo, así que mezclar series
    # de dos descargas dejaría un salto falso el día en que se unen.
    keep_from = date.today() - timedelta(days=365 * (HISTORY_YEARS + 1))
    bars = [(day, close) for day, close in parsed["bars"] if day >= keep_from]
    row.closes = encode_closes(bars)
    row.currency = parsed["currency"]
    row.first_day = bars[0][0] if bars else None
    row.last_day = bars[-1][0] if bars else None

    known = {
        (action.day, action.kind)
        for action in db.scalars(select(CorporateAction).where(CorporateAction.symbol == symbol))
    }
    for day, ratio in parsed["splits"]:
        if (day, "split") not in known:
            db.add(CorporateAction(symbol=symbol, day=day, kind="split", ratio=ratio))
    for day, amount in parsed["dividends"]:
        if (day, "dividend") not in known:
            db.add(CorporateAction(symbol=symbol, day=day, kind="dividend", amount=amount))
    return len(bars)


# --- Qué se descarga --------------------------------------------------------


def history_universe(db, since: Optional[date] = None) -> list[str]:
    """Valores que necesitan histórico: el índice, lo que está en cartera y lo
    que se ha comprado o vendido en el periodo que mide la rentabilidad."""
    since = since or date.today() - timedelta(days=365 * HISTORY_YEARS)
    symbols = {BENCHMARK}
    for model in (Holding, DerivativeHolding):
        symbols.update(
            db.scalars(select(Ticker.symbol).join(model, model.ticker_id == Ticker.id)).all()
        )
    trade_type = func.lower(Trade.trade_type)
    symbols.update(
        db.scalars(
            select(Ticker.symbol)
            .join(Trade, Trade.ticker_id == Ticker.id)
            .where(
                Trade.reported_date >= since,
                or_(trade_type.in_(OPEN_MARKET_TYPES), trade_type.like("sale%")),
            )
            .distinct()
        ).all()
    )
    return sorted(symbol for symbol in symbols if symbol)


def refresh_order(db, symbols: list[str], now: datetime) -> list[str]:
    """Primero el índice, luego lo que nunca se pidió y luego lo más viejo."""
    fetched = dict(
        db.execute(
            select(PriceHistory.symbol, PriceHistory.fetched_at).where(
                PriceHistory.symbol.in_(symbols)
            )
        ).all()
    )
    due = [
        symbol
        for symbol in symbols
        if symbol not in fetched or now - fetched[symbol] >= REFRESH_AFTER
    ]
    return sorted(
        due,
        key=lambda symbol: (symbol != BENCHMARK, symbol in fetched, fetched.get(symbol) or now, symbol),
    )


def refresh_history(max_symbols: int = MAX_SYMBOLS_PER_RUN, verbose: bool = True) -> dict[str, int]:
    prepare_database()
    now = utcnow()
    stats = {"universe": 0, "fetched": 0, "empty": 0}
    with SessionLocal() as db:
        universe = history_universe(db)
        stats["universe"] = len(universe)
        batch = refresh_order(db, universe, now)[:max_symbols]

    for symbol in batch:
        parsed = fetch_history(symbol, HISTORY_YEARS)
        with SessionLocal() as db:
            sessions = store_history(db, symbol, parsed, now)
            db.commit()
        if parsed and parsed["bars"]:
            stats["fetched"] += 1
        else:
            stats["empty"] += 1
        if verbose:
            print(f"  {'ok' if sessions else '--'} {symbol:10s} {sessions} sesiones", flush=True)
    return stats


# --- Splits y dividendos sobre una posición ---------------------------------


def split_factor(actions: Iterable[CorporateAction], since: date) -> Decimal:
    """Títulos de hoy por cada título declarado en `since`."""
    factor = Decimal(1)
    for action in actions:
        if action.kind == "split" and action.day > since and action.ratio:
            factor *= to_decimal(action.ratio)
    return factor


def dividends_since(actions: Iterable[CorporateAction], since: date) -> Decimal:
    """Dividendo por acción de hoy repartido después de `since`.

    Yahoo da los importes ya ajustados a los splits posteriores, así que se
    multiplican por los títulos de hoy, no por los declarados.
    """
    return sum(
        (to_decimal(action.amount) for action in actions if action.kind == "dividend" and action.day > since and action.amount),
        Decimal(0),
    )


if __name__ == "__main__":
    print("Descargando históricos de cotización...")
    print(refresh_history())
