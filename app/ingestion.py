from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import ensure_schema, get_engine
from app.models import Base, Politician, Ticker, Trade
from app.scraper import parse_senate_filing

DEFAULT_PROFILE = {"chamber": "Senate", "state": "California", "party": "Unknown"}


def _parse_reported_date(value: Any) -> Optional[date]:
    """El parser deja la fecha como 'unknown' si el filing no la trae."""
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _commit_one_by_one(
    db,
    pending: list[tuple[dict[str, Any], dict[str, object]]],
) -> list[dict[str, object]]:
    """Reinserta el lote fila a fila, descartando las que ya existan."""
    saved: list[dict[str, object]] = []
    for trade_fields, summary in pending:
        try:
            db.add(Trade(**trade_fields))
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        saved.append(summary)
    return saved


def load_trade_records_into_db(
    records: Iterable[dict[str, Any]],
    database_url: Optional[str] = None,
    profile: Optional[dict[str, str]] = None,
    notes: str = "Imported from Senate filing",
) -> list[dict[str, object]]:
    """Guarda registros ya parseados en una sola sesión, saltando duplicados.

    Las fuentes republican el histórico completo en cada pasada, así que sin el
    filtro por identidad cada ciclo de polling duplicaría la base entera.
    """
    records = list(records)
    if not records:
        return []

    engine = get_engine(database_url or "sqlite:///./thewhalefiles.db")
    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    defaults = {**DEFAULT_PROFILE, **(profile or {})}

    with SessionLocal() as db:
        politicians = {person.name: person for person in db.scalars(select(Politician)).all()}
        tickers = {ticker.symbol: ticker for ticker in db.scalars(select(Ticker)).all()}
        known_trades = set(
            db.execute(
                select(
                    Trade.politician_id,
                    Trade.ticker_id,
                    Trade.trade_type,
                    Trade.amount,
                    Trade.reported_date,
                )
            ).all()
        )

        saved_records: list[dict[str, object]] = []
        pending: list[tuple[dict[str, Any], dict[str, object]]] = []
        for record in records:
            reported_date = _parse_reported_date(record.get("reported_date"))
            if reported_date is None:
                continue

            politician_name = str(record.get("politician_name") or "").strip()
            ticker_symbol = str(record.get("ticker") or "").strip().upper()
            if not politician_name or not ticker_symbol:
                continue

            politician = politicians.get(politician_name)
            if politician is None:
                # Cada fuente sabe más que los valores por defecto sobre a qué
                # cámara y estado pertenece quien firma el filing.
                profile_fields = {
                    key: str(record[key])
                    for key in ("chamber", "state", "party", "category")
                    if record.get(key)
                }
                politician = Politician(name=politician_name, **{**defaults, **profile_fields})
                db.add(politician)
                db.flush()
                politicians[politician_name] = politician

            ticker = tickers.get(ticker_symbol)
            if ticker is None:
                ticker = Ticker(symbol=ticker_symbol, name=ticker_symbol)
                db.add(ticker)
                db.flush()
                tickers[ticker_symbol] = ticker

            trade_type = str(record.get("trade_type") or "Unknown")
            amount = float(record.get("amount") or 0.0)
            identity = (politician.id, ticker.id, trade_type, amount, reported_date)
            if identity in known_trades:
                continue
            known_trades.add(identity)

            trade_fields = {
                "politician_id": politician.id,
                "ticker_id": ticker.id,
                "trade_type": trade_type,
                "amount": amount,
                "reported_date": reported_date,
                "notes": notes,
            }
            db.add(Trade(**trade_fields))

            summary = {
                "politician": politician_name,
                "ticker": ticker_symbol,
                "trade_type": trade_type,
                "amount": amount,
                "reported_date": reported_date.isoformat(),
            }
            saved_records.append(summary)
            pending.append((trade_fields, summary))

        try:
            db.commit()
        except IntegrityError:
            # Otro proceso insertó la misma operación entre la lectura y el
            # commit. Se reintenta fila a fila para no perder el lote entero.
            db.rollback()
            saved_records = _commit_one_by_one(db, pending)

    return saved_records


def load_filing_into_db(
    raw_text: str,
    politician_name: str,
    database_url: Optional[str] = None,
) -> list[dict[str, object]]:
    """Parse a filing and store the transactions in the database."""
    trades = parse_senate_filing(raw_text, politician_name)
    return load_trade_records_into_db(trades, database_url=database_url)
