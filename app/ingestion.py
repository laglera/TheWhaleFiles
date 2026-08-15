from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database import ensure_schema, get_engine
from app.models import Base, Politician, Ticker, Trade
from app.scraper import parse_senate_filing


def load_filing_into_db(
    raw_text: str,
    politician_name: str,
    database_url: Optional[str] = None,
) -> list[dict[str, object]]:
    """Parse a filing and store the transactions in the database."""
    trades = parse_senate_filing(raw_text, politician_name)
    engine = get_engine(database_url or "sqlite:///./thewhalefiles.db")
    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with SessionLocal() as db:
        politician = db.scalar(select(Politician).where(Politician.name == politician_name))
        if politician is None:
            politician = Politician(
                name=politician_name,
                chamber="Senate",
                state="California",
                party="Unknown",
            )
            db.add(politician)
            db.flush()

        saved_records: list[dict[str, object]] = []
        for trade in trades:
            ticker_symbol = str(trade["ticker"])
            ticker = db.scalar(select(Ticker).where(Ticker.symbol == ticker_symbol))
            if ticker is None:
                ticker = Ticker(symbol=ticker_symbol, name=ticker_symbol)
                db.add(ticker)
                db.flush()

            trade_record = Trade(
                politician_id=politician.id,
                ticker_id=ticker.id,
                trade_type=str(trade["trade_type"]),
                amount=float(trade["amount"]),
                reported_date=datetime.strptime(str(trade["reported_date"]), "%Y-%m-%d").date(),
                notes="Imported from Senate filing",
            )
            db.add(trade_record)
            db.flush()

            saved_records.append(
                {
                    "politician": politician.name,
                    "ticker": ticker_symbol,
                    "trade_type": trade_record.trade_type,
                    "amount": float(trade_record.amount),
                    "reported_date": trade_record.reported_date.isoformat(),
                }
            )

        db.commit()

    return saved_records
