from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.ingestion import load_filing_into_db
from app.models import Politician, Trade

app = FastAPI(title="TheWhaleFiles", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
init_db()


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)) -> Any:
    politicians = db.scalars(select(Politician)).all()
    recent_trades = db.scalars(
        select(Trade).order_by(Trade.reported_date.desc()).limit(10)
    ).all()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "politicians": politicians,
            "recent_trades": recent_trades,
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
