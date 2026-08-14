from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.ingestion import load_filing_into_db
from app.models import Politician, Trade

app = FastAPI(title="TheWhaleFiles", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
init_db()


@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    db: Session = Depends(get_db),
    chamber: Optional[str] = None,
    party: Optional[str] = None,
    q: Optional[str] = None,
) -> Any:
    filters = []
    if chamber:
        filters.append(Politician.chamber == chamber)
    if party:
        filters.append(Politician.party == party)

    politician_query = select(Politician)
    if filters:
        politician_query = politician_query.where(*filters)
    politician_query = politician_query.order_by(Politician.name)

    politicians = db.scalars(politician_query).all()

    if q:
        search_value = q.strip().lower()
        politicians = [
            politician
            for politician in politicians
            if search_value in politician.name.lower()
            or any(search_value in trade.ticker.symbol.lower() for trade in politician.trades)
        ]

    trade_query = select(Trade).join(Politician).join(Trade.ticker)
    if chamber:
        trade_query = trade_query.where(Politician.chamber == chamber)
    if party:
        trade_query = trade_query.where(Politician.party == party)
    if q:
        search_value = q.strip().lower()
        trade_query = trade_query.where(
            or_(
                func.lower(Politician.name).contains(search_value),
                func.lower(Trade.trade_type).contains(search_value),
                func.lower(Trade.ticker.symbol).contains(search_value),
            )
        )

    recent_trades = db.scalars(trade_query.order_by(Trade.reported_date.desc()).limit(10)).all()
    all_trades = db.scalars(select(Trade)).all()
    total_amount = sum(float(trade.amount) for trade in all_trades)

    unique_chambers = db.scalars(select(Politician.chamber).distinct()).all()
    unique_parties = db.scalars(select(Politician.party).distinct()).all()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "politicians": politicians,
            "recent_trades": recent_trades,
            "total_trades": len(all_trades),
            "total_amount": total_amount,
            "total_politicians": len(db.scalars(select(Politician)).all()),
            "active_chamber": chamber,
            "active_party": party,
            "active_query": q or "",
            "chambers": [value for value in unique_chambers if value],
            "parties": [value for value in unique_parties if value],
        },
    )


@app.get("/api/trades")
def get_trades(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    trades = db.scalars(select(Trade).order_by(Trade.reported_date.desc())).all()
    result = []
    for trade in trades:
        result.append(
            {
                "id": trade.id,
                "politician": trade.politician.name,
                "chamber": trade.politician.chamber,
                "ticker": trade.ticker.symbol,
                "trade_type": trade.trade_type,
                "amount": float(trade.amount),
                "reported_date": trade.reported_date.isoformat(),
            }
        )
    return result


@app.get("/api/politicians")
def get_politicians(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    politicians = db.scalars(select(Politician)).all()
    return [
        {
            "id": politician.id,
            "name": politician.name,
            "chamber": politician.chamber,
            "state": politician.state,
            "party": politician.party,
            "trade_count": len(politician.trades),
        }
        for politician in politicians
    ]


@app.get("/api/politicians/{politician_id}")
def get_politician_detail(politician_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    politician = db.get(Politician, politician_id)
    if not politician:
        raise HTTPException(status_code=404, detail="Politician not found")

    return {
        "id": politician.id,
        "name": politician.name,
        "chamber": politician.chamber,
        "state": politician.state,
        "party": politician.party,
        "trades": [
            {
                "id": trade.id,
                "ticker": trade.ticker.symbol,
                "trade_type": trade.trade_type,
                "amount": float(trade.amount),
                "reported_date": trade.reported_date.isoformat(),
            }
            for trade in politician.trades
        ],
    }


@app.get("/politicians/{politician_id}", response_class=HTMLResponse)
def politician_detail_page(
    request: Request,
    politician_id: int,
    db: Session = Depends(get_db),
) -> Any:
    politician = db.get(Politician, politician_id)
    if not politician:
        raise HTTPException(status_code=404, detail="Politician not found")

    ordered_trades = sorted(politician.trades, key=lambda trade: trade.reported_date, reverse=True)
    total_amount = sum(float(trade.amount) for trade in ordered_trades)

    return templates.TemplateResponse(
        "politician_detail.html",
        {
            "request": request,
            "politician": politician,
            "trades": ordered_trades,
            "total_amount": total_amount,
        },
    )


@app.post("/api/load-sample-filing")
def load_sample_filing() -> dict[str, Any]:
    sample_file = Path("app/data/sample_senate_filing.txt")
    if not sample_file.exists():
        raise HTTPException(status_code=404, detail="Sample filing not found")

    raw_text = sample_file.read_text(encoding="utf-8")
    imported_trades = load_filing_into_db(raw_text, "Alex Morgan")
    return {
        "politician": "Alex Morgan",
        "imported_count": len(imported_trades),
        "records": imported_trades,
    }
