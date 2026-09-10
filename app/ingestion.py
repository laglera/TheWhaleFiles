from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import DATABASE_URL, get_engine, prepare_database
from app.models import Politician, Ticker, Trade
from app.names import clean_person_name
from app.scraper import parse_senate_filing

LOGGER = logging.getLogger(__name__)

DEFAULT_PROFILE = {"chamber": "Senate", "state": "California", "party": "Unknown"}


def _parse_date(value: Any) -> Optional[date]:
    """Fecha ISO de la fuente, o None si no la trae o no es una fecha.

    Nunca se sustituye por un valor por defecto: una operación sin fecha
    verificable no entra en la base.
    """
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _clean_dates(
    record: dict[str, Any],
    rejected: Optional[dict[str, int]] = None,
) -> Optional[tuple[date, Optional[date]]]:
    """Valida el par (publicación, operación) de un registro.

    Devuelve None si la operación no puede guardarse. La fecha de operación
    vuelve como None cuando el propio filing se contradice: la web prefiere no
    enseñar ninguna fecha antes que enseñar una imposible.

    El detalle de cada descarte va a DEBUG y el recuento lo resume quien llama:
    las fuentes republican su histórico entero en cada pasada, así que a nivel
    WARNING los mismos cincuenta errores de 2016 se repetirían cada cuarto de
    hora.
    """
    rejected = {} if rejected is None else rejected
    reported = _parse_date(record.get("reported_date"))
    if reported is None:
        rejected["sin_fecha_de_publicación"] = rejected.get("sin_fecha_de_publicación", 0) + 1
        return None

    today = date.today()
    # Un filing no puede haberse publicado en el futuro. Si la fuente lo dice,
    # el dato está corrupto y la operación entera queda fuera.
    if reported > today:
        LOGGER.debug(
            "Descartada operación con fecha de publicación futura: %s %s %s",
            record.get("politician_name"),
            record.get("ticker"),
            reported.isoformat(),
        )
        rejected["publicación_futura"] = rejected.get("publicación_futura", 0) + 1
        return None

    traded = _parse_date(record.get("transaction_date"))
    # Nadie declara una operación antes de ejecutarla: si la fecha de operación
    # es posterior a la publicación (o al día de hoy), el año viene mal escrito
    # en el filing original y no hay forma de saber cuál era el bueno.
    if traded is not None and (traded > reported or traded > today):
        LOGGER.debug(
            "Fecha de operación imposible (%s, publicada el %s): %s %s. Se guarda sin ella.",
            traded.isoformat(),
            reported.isoformat(),
            record.get("politician_name"),
            record.get("ticker"),
        )
        rejected["operación_posterior_a_su_filing"] = (
            rejected.get("operación_posterior_a_su_filing", 0) + 1
        )
        traded = None

    return reported, traded


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

    # Sin URL explícita, la misma base que sirve la web. Antes se caía a un
    # SQLite fijo: con DATABASE_URL apuntando a Postgres, el polling y
    # `repair_dates` escribían las operaciones del Congreso en un fichero local
    # que nadie leía, y producción se quedaba sin ellas.
    engine = get_engine(database_url or DATABASE_URL)
    prepare_database(engine)
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
                    Trade.transaction_date,
                )
            ).all()
        )

        saved_records: list[dict[str, object]] = []
        pending: list[tuple[dict[str, Any], dict[str, object]]] = []
        rejected: dict[str, int] = {}
        for record in records:
            dates = _clean_dates(record, rejected)
            if dates is None:
                continue
            reported_date, transaction_date = dates

            # Se normaliza en la entrada: si no, cada variante del mismo nombre
            # que publica la fuente acaba siendo una ficha distinta.
            politician_name = clean_person_name(str(record.get("politician_name") or ""))
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
            identity = (
                politician.id,
                ticker.id,
                trade_type,
                amount,
                reported_date,
                transaction_date,
            )
            if identity in known_trades:
                continue
            known_trades.add(identity)

            trade_fields = {
                "politician_id": politician.id,
                "ticker_id": ticker.id,
                "trade_type": trade_type,
                "amount": amount,
                "reported_date": reported_date,
                "transaction_date": transaction_date,
                "notes": notes,
            }
            db.add(Trade(**trade_fields))

            summary = {
                "politician": politician_name,
                "ticker": ticker_symbol,
                "trade_type": trade_type,
                "amount": amount,
                "reported_date": reported_date.isoformat(),
                "transaction_date": transaction_date.isoformat() if transaction_date else None,
            }
            saved_records.append(summary)
            pending.append((trade_fields, summary))

        if rejected:
            LOGGER.info(
                "Fechas descartadas sobre %s registros leídos: %s",
                len(records),
                ", ".join(f"{motivo}: {total}" for motivo, total in sorted(rejected.items())),
            )

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
