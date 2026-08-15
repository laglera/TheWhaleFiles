from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.i18n import DEFAULT_LANG, get_translations, normalise_lang
from app.ingestion import load_filing_into_db
from app.models import Politician, Ticker, Trade
from app.scheduler import start_polling_loop
from app.sources import poll_official_sources

app = FastAPI(title="TheWhaleFiles", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
init_db()

BUY_TYPES = {"purchase", "buy", "p"}
SELL_TYPES = {"sale", "sell", "s", "sale (full)", "sale (partial)"}


def trade_side(trade_type: str) -> str:
    """Normaliza los tipos declarados en los filings a buy / sell / other."""
    value = (trade_type or "").strip().lower()
    if value in BUY_TYPES:
        return "buy"
    if value in SELL_TYPES or value.startswith("sale"):
        return "sell"
    return "other"


def compact_money(value: float) -> str:
    """Mismo formato compacto que el macro `money` de las plantillas."""
    amount = float(value or 0)
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:,.1f}B"
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:,.1f}M"
    if amount >= 1_000:
        return f"${amount / 1_000:,.0f}K"
    return f"${amount:,.0f}"


def accent_slot(value: Any) -> int:
    """Índice de acento estable (0-7) para colorear avatares por entidad."""
    text = str(value or "")
    return sum(ord(char) for char in text) % 8


def _load_photo_index() -> dict[str, str]:
    """Retratos oficiales (dominio público, unitedstates/images) por nombre."""
    photo_file = Path("app/data/politician_photos.json")
    if not photo_file.exists():
        return {}
    with photo_file.open(encoding="utf-8") as handle:
        return json.load(handle)


PHOTO_INDEX = _load_photo_index()


def photo_url(name: str) -> Optional[str]:
    """Miniatura para avatares (140px de alto)."""
    filename = PHOTO_INDEX.get(name or "")
    return f"/static/photos/{filename}" if filename else None


def photo_url_lg(name: str) -> Optional[str]:
    """Retrato a resolución completa (450x550) para la ficha."""
    filename = PHOTO_INDEX.get(name or "")
    return f"/static/photos/lg/{filename}" if filename else None


templates.env.filters["trade_side"] = trade_side
templates.env.filters["accent_slot"] = accent_slot
templates.env.filters["photo_url"] = photo_url
templates.env.filters["photo_url_lg"] = photo_url_lg

LANG_COOKIE = "twf_lang"


def resolve_lang(request: Request, lang: Optional[str]) -> str:
    """El parámetro `?lang=` manda; si no, la cookie; si no, español."""
    if lang:
        return normalise_lang(lang)
    return normalise_lang(request.cookies.get(LANG_COOKIE, DEFAULT_LANG))


def lang_switch_url(request: Request, target: str) -> str:
    """Cambia de idioma conservando los filtros de la URL actual."""
    raw_query = request.scope.get("query_string", b"") or b""
    if isinstance(raw_query, bytes):
        raw_query = raw_query.decode("utf-8", "ignore")
    params = [(key, value) for key, value in parse_qsl(raw_query) if key != "lang"]
    params.append(("lang", target))
    return "?" + urlencode(params)


def render(
    request: Request,
    template: str,
    context: dict[str, Any],
    lang: str,
) -> Any:
    other_lang = "en" if lang == "es" else "es"
    context = {
        **context,
        "request": request,
        "lang": lang,
        "other_lang": other_lang,
        "lang_switch_url": lang_switch_url(request, other_lang),
        "t": get_translations(lang),
    }
    response = templates.TemplateResponse(template, context)
    response.set_cookie(LANG_COOKIE, lang, max_age=60 * 60 * 24 * 365, samesite="lax")
    return response


@app.on_event("startup")
def startup_event() -> None:
    # Comentado para evitar segfault al iniciar - descomentar si es necesario
    # start_polling_loop()
    pass


@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    db: Session = Depends(get_db),
    chamber: Optional[str] = None,
    party: Optional[str] = None,
    q: Optional[str] = None,
    category: Optional[str] = None,
    lang: Optional[str] = None,
) -> Any:
    search_value = q.strip().lower() if q else ""

    scope_filters = []
    if chamber:
        scope_filters.append(Politician.chamber == chamber)
    if party:
        scope_filters.append(Politician.party == party)
    if category in ("congress", "business"):
        scope_filters.append(Politician.category == category)

    trade_query = select(Trade).join(Trade.politician).join(Trade.ticker)
    if scope_filters:
        trade_query = trade_query.where(*scope_filters)
    if search_value:
        trade_query = trade_query.where(
            or_(
                func.lower(Politician.name).contains(search_value),
                func.lower(Trade.trade_type).contains(search_value),
                func.lower(Ticker.symbol).contains(search_value),
            )
        )

    recent_trades = db.scalars(
        trade_query.order_by(Trade.reported_date.desc(), Trade.id.desc()).limit(12)
    ).all()

    # Agregados sobre el mismo filtro, calculados en SQL para no traer 30k filas.
    scoped_ids = trade_query.with_only_columns(Trade.id).subquery()
    totals_query = (
        select(
            func.count(Trade.id),
            func.coalesce(func.sum(Trade.amount), 0.0),
            func.count(func.distinct(Trade.politician_id)),
        )
        .select_from(Trade)
        .join(scoped_ids, scoped_ids.c.id == Trade.id)
    )
    total_trades, total_amount, total_politicians = db.execute(totals_query).one()
    last_reported = recent_trades[0].reported_date if recent_trades else None

    side_rows = db.execute(
        select(Trade.trade_type, func.count(Trade.id))
        .select_from(Trade)
        .join(scoped_ids, scoped_ids.c.id == Trade.id)
        .group_by(Trade.trade_type)
    ).all()
    side_counts = {"buy": 0, "sell": 0, "other": 0}
    for trade_type, count in side_rows:
        side_counts[trade_side(trade_type)] += count

    top_tickers = db.execute(
        select(
            Ticker.symbol,
            func.count(Trade.id).label("operations"),
            func.coalesce(func.sum(Trade.amount), 0.0).label("volume"),
        )
        .select_from(Trade)
        .join(scoped_ids, scoped_ids.c.id == Trade.id)
        .join(Ticker, Ticker.id == Trade.ticker_id)
        .group_by(Ticker.symbol)
        .order_by(func.count(Trade.id).desc())
        .limit(6)
    ).all()

    # Ranking de políticos: conteo y volumen resueltos en una sola consulta agregada.
    politician_query = (
        select(
            Politician,
            func.count(Trade.id).label("operations"),
            func.coalesce(func.sum(Trade.amount), 0.0).label("volume"),
        )
        .select_from(Trade)
        .join(scoped_ids, scoped_ids.c.id == Trade.id)
        .join(Politician, Politician.id == Trade.politician_id)
        .group_by(Politician.id)
        .order_by(func.count(Trade.id).desc())
    )
    politician_rows = db.execute(politician_query).all()
    politicians = [
        {
            "id": politician.id,
            "name": politician.name,
            "chamber": politician.chamber,
            "state": politician.state,
            "party": politician.party,
            "category": politician.category,
            "operations": operations,
            "volume": float(volume),
        }
        for politician, operations, volume in politician_rows
    ]
    visible_politicians = politicians[:24]

    # Clasificación de los mayores inversores: por capital declarado, no por nº de operaciones.
    leaderboard = sorted(politicians, key=lambda item: item["volume"], reverse=True)[:10]

    unique_chambers = db.scalars(select(Politician.chamber).distinct()).all()
    unique_parties = db.scalars(select(Politician.party).distinct()).all()

    return render(
        request,
        "index.html",
        {
            "politicians": visible_politicians,
            "leaderboard": leaderboard,
            "hidden_politicians": max(len(politicians) - len(visible_politicians), 0),
            "recent_trades": recent_trades,
            "total_trades": total_trades,
            "total_amount": float(total_amount),
            "total_politicians": total_politicians,
            "last_reported": last_reported,
            "side_counts": side_counts,
            "top_tickers": [
                {"symbol": symbol, "operations": operations, "volume": float(volume)}
                for symbol, operations, volume in top_tickers
            ],
            "active_chamber": chamber,
            "active_party": party,
            "active_category": category or "",
            "active_query": q or "",
            "has_filters": bool(chamber or party or search_value or category),
            "chambers": [value for value in unique_chambers if value],
            "parties": [value for value in unique_parties if value],
        },
        resolve_lang(request, lang),
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
    lang: Optional[str] = None,
) -> Any:
    politician = db.get(Politician, politician_id)
    if not politician:
        raise HTTPException(status_code=404, detail="Politician not found")

    ordered_trades = sorted(politician.trades, key=lambda trade: trade.reported_date, reverse=True)
    total_amount = sum(float(trade.amount) for trade in ordered_trades)

    side_counts = {"buy": 0, "sell": 0, "other": 0}
    ticker_volume: dict[str, dict[str, Any]] = {}
    for trade in ordered_trades:
        side_counts[trade_side(trade.trade_type)] += 1
        entry = ticker_volume.setdefault(
            trade.ticker.symbol, {"symbol": trade.ticker.symbol, "operations": 0, "volume": 0.0}
        )
        entry["operations"] += 1
        entry["volume"] += float(trade.amount)

    top_tickers = sorted(ticker_volume.values(), key=lambda item: item["operations"], reverse=True)[:5]
    visible_trades = ordered_trades[:60]

    # No hay campo de biografía: se resume el perfil a partir de lo declarado.
    classified = side_counts["buy"] + side_counts["sell"]
    resolved_lang = resolve_lang(request, lang)
    strings = get_translations(resolved_lang)

    if ordered_trades:
        favourite = ""
        if top_tickers:
            favourite = strings["profile_bio_fav"].format(
                symbol=escape(top_tickers[0]["symbol"]),
                ops=top_tickers[0]["operations"],
            )
        bio_html = Markup(
            strings["profile_bio"].format(
                trades=f"{len(ordered_trades):,.0f}",
                tickers=len(ticker_volume),
                first=ordered_trades[-1].reported_date.strftime("%m/%Y"),
                last=ordered_trades[0].reported_date.strftime("%m/%Y"),
                total=escape(compact_money(total_amount)),
                ratio=round(side_counts["buy"] / classified * 100) if classified else 0,
                favourite=favourite,
            )
        )
    else:
        bio_html = Markup(escape(strings["profile_bio_empty"]))

    return render(
        request,
        "politician_detail.html",
        {
            "politician": politician,
            "trades": visible_trades,
            "total_trades": len(ordered_trades),
            "hidden_trades": max(len(ordered_trades) - len(visible_trades), 0),
            "total_amount": total_amount,
            "side_counts": side_counts,
            "top_tickers": top_tickers,
            "bio_html": bio_html,
        },
        resolved_lang,
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


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "TheWhaleFiles"}


@app.post("/api/poll-sources")
def poll_sources_endpoint() -> dict[str, Any]:
    imported = poll_official_sources()
    return {
        "imported_count": len(imported),
        "records": imported[:10],
    }
