from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from contextlib import asynccontextmanager
from functools import lru_cache
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, joinedload
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.amounts import bracket_for, bracket_label, short_money, volume_range
from app.database import SessionLocal, get_db, init_db, prepare_database
from app.i18n import DEFAULT_LANG, get_translations, normalise_lang
from app.ingestion import load_filing_into_db
from app.models import Politician, Ticker, Trade
from app.prices import provider_name as price_source
from app.performance import load_performance
from app.prices import value_derivatives, value_holdings
from app.runtime import is_serverless, utcnow
from app.scheduler import polling_enabled, start_polling_loop, stop_polling_loop
from app.security import rate_limit_middleware, require_admin, security_headers_middleware
from app.sources import poll_official_sources

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# Rutas ancladas al paquete, no al directorio desde el que se lanzó el proceso.
# En una función serverless el proceso arranca desde otro sitio y "app/static"
# no existe: la web se quedaría sin hoja de estilos ni plantillas.
APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"
DATA_DIR = APP_DIR / "data"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Ciclo de vida de la aplicación.

    `@app.on_event` quedó deprecado y ya no existe en las versiones nuevas de
    Starlette. El hilo de polling corre aparte: no bloquea el arranque y no
    comparte conexión con las peticiones web. Se desactiva con ENABLE_POLLING=0.
    """
    if polling_enabled():
        start_polling_loop()
    yield
    stop_polling_loop()


class HeadAsGetMiddleware:
    """Responde a HEAD como a GET, sin cuerpo.

    FastAPI sólo registra GET en estas rutas y a HEAD contestaba 405. Es lo que
    usan los monitores de disponibilidad y muchos previsualizadores de enlaces:
    la portada parecía caída sin estarlo.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "HEAD":
            await self.app(scope, receive, send)
            return

        async def send_without_body(message):
            if message["type"] == "http.response.body":
                message = {**message, "body": b""}
            await send(message)

        await self.app({**scope, "method": "GET"}, receive, send_without_body)


app = FastAPI(title="TheWhaleFiles", version="0.1.0", lifespan=lifespan)
# Límite por IP en la API. Se registra antes que las cabeceras para que éstas
# lo envuelvan: un 429 también lleva su CSP.
app.middleware("http")(rate_limit_middleware)
# Cabeceras de seguridad y nonce de CSP para los scripts en línea.
app.middleware("http")(security_headers_middleware)
# El último añadido envuelve a todos: la petición llega ya como GET.
app.add_middleware(HeadAsGetMiddleware)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# init_db() siembra la base la primera vez, y esa ingesta tarda minutos. En
# serverless eso caería dentro de la primera petición y la tumbaría por
# timeout: allí sólo se comprueba el esquema, y los datos se cargan aparte.
if is_serverless():
    prepare_database()
else:
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


# Lo que no es compra ni venta, con nombre propio: un canje del Congreso o una
# concesión de acciones de la SEC no son lo mismo, y "sin clasificar" los
# confundía a todos con un dato que falta.
TRADE_KINDS = {
    "exchange": "exchange",
    "grant": "grant",
    "option exercise": "option",
    "tax withholding": "tax",
    "gift": "gift",
    "conversion": "conversion",
    "disposition": "disposition",
}


def trade_kind(trade_type: str) -> str:
    """Tipo de operación para la etiqueta: buy, sell o el tipo concreto."""
    side = trade_side(trade_type)
    if side != "other":
        return side
    return TRADE_KINDS.get((trade_type or "").strip().lower(), "other")


# Compras y ventas en mercado, en SQL. Es lo único que mueve dinero por
# decisión propia: una concesión de acciones, una retención fiscal o una
# donación no son inversión, y sumarlas convertía los 141.000 millones del
# paquete de Musk en "capital declarado".
_LOWER_TYPE = func.lower(Trade.trade_type)
OPEN_MARKET = or_(
    _LOWER_TYPE.in_(BUY_TYPES),
    _LOWER_TYPE.in_(SELL_TYPES),
    _LOWER_TYPE.like("sale%"),
)
OPEN_MARKET_VOLUME = func.coalesce(
    func.sum(case((OPEN_MARKET, Trade.amount), else_=0.0)), 0.0
)
OPEN_MARKET_COUNT = func.coalesce(func.sum(case((OPEN_MARKET, 1), else_=0)), 0)


def published():
    """Operaciones cuyo filing ya se ha publicado.

    La ingesta descarta los filings fechados en el futuro, pero una base
    cargada antes de ese filtro los conserva: en producción abría la portada
    una compra "publicada" el 26/12/2026. Es un error de escritura en el
    documento original, y no se enseña como lo más reciente.
    """
    return Trade.reported_date <= date.today()


# Plazo máximo de la STOCK Act entre la operación y su declaración.
LEGAL_DEADLINE_DAYS = 45


# Más de un año entre operar y declarar casi nunca es un retraso de verdad:
# suele ser el año mal escrito en el filing (una operación "de 2015"
# declarada en 2025). Se marca como dudosa y no entra en el retraso medio.
SUSPECT_LAG_DAYS = 365


def disclosure_lag(trade: Trade) -> Optional[int]:
    """Días entre la operación y la publicación del filing que la declara."""
    if trade.transaction_date is None or trade.reported_date is None:
        return None
    return (trade.reported_date - trade.transaction_date).days


def lag_flag(trade: Trade) -> Optional[str]:
    """"suspect" si el retraso es inverosímil, "late" si incumple la STOCK Act.

    El plazo de 45 días es el del Congreso; los directivos declaran con el
    Form 4 en dos días hábiles y no se les mide con esa vara.
    """
    lag = disclosure_lag(trade)
    if lag is None:
        return None
    if lag > SUSPECT_LAG_DAYS:
        return "suspect"
    if lag > LEGAL_DEADLINE_DAYS and trade.politician.category == "congress":
        return "late"
    return None


def compact_money(value: float) -> str:
    """Mismo formato compacto que el macro `money` de las plantillas."""
    amount = float(value or 0)
    # Umbrales tras redondear: $999,96M se escribía "$1,000.0M".
    if amount >= 999_950_000:
        return f"${amount / 1_000_000_000:,.1f}B"
    if amount >= 999_500:
        return f"${amount / 1_000_000:,.1f}M"
    if amount >= 999.5:
        return f"${amount / 1_000:,.0f}K"
    return f"${amount:,.0f}"


def accent_slot(value: Any) -> int:
    """Índice de acento estable (0-7) para colorear avatares por entidad."""
    text = str(value or "")
    return sum(ord(char) for char in text) % 8


def _load_photo_index() -> dict[str, str]:
    """Retratos oficiales (dominio público, unitedstates/images) por nombre."""
    photo_file = DATA_DIR / "politician_photos.json"
    if not photo_file.exists():
        return {}
    with photo_file.open(encoding="utf-8") as handle:
        return json.load(handle)


PHOTO_INDEX = _load_photo_index()

# Retratos traídos de Wikimedia Commons, para quien no tiene foto oficial (los
# empresarios, sobre todo). Se cachean en memoria porque el índice se consulta
# una vez por avatar y la lista entera cabe de sobra.
_REMOTE_PHOTOS: dict[str, dict[str, Optional[str]]] = {}
_REMOTE_PHOTOS_AT: Optional[datetime] = None
REMOTE_PHOTO_TTL = timedelta(minutes=5)
# Las rutas síncronas corren en un pool de hilos: sin cerrojo, si la caché
# caducaba con varias páginas a medio pintar, cada hilo relanzaba la consulta.
# Con él la relanza uno solo y los demás siguen con el índice anterior.
_REMOTE_PHOTOS_LOCK = threading.Lock()


def remote_photo_index() -> dict[str, dict[str, Optional[str]]]:
    global _REMOTE_PHOTOS, _REMOTE_PHOTOS_AT

    now = utcnow()
    if _REMOTE_PHOTOS_AT and now - _REMOTE_PHOTOS_AT < REMOTE_PHOTO_TTL:
        return _REMOTE_PHOTOS

    if not _REMOTE_PHOTOS_LOCK.acquire(blocking=_REMOTE_PHOTOS_AT is None):
        return _REMOTE_PHOTOS
    try:
        # Otro hilo pudo refrescarlo mientras éste esperaba el cerrojo.
        if _REMOTE_PHOTOS_AT and utcnow() - _REMOTE_PHOTOS_AT < REMOTE_PHOTO_TTL:
            return _REMOTE_PHOTOS
        return _reload_remote_photos(now)
    finally:
        _REMOTE_PHOTOS_LOCK.release()


def _reload_remote_photos(now: datetime) -> dict[str, dict[str, Optional[str]]]:
    global _REMOTE_PHOTOS, _REMOTE_PHOTOS_AT

    with SessionLocal() as db:
        rows = db.execute(
            select(
                Politician.name,
                Politician.photo_remote_url,
                Politician.photo_author,
                Politician.photo_license,
            ).where(Politician.photo_remote_url.is_not(None))
        ).all()

    _REMOTE_PHOTOS = {
        name: {"url": url, "author": author, "license": licence}
        for name, url, author, licence in rows
    }
    _REMOTE_PHOTOS_AT = now
    return _REMOTE_PHOTOS


def photo_url(name: str) -> Optional[str]:
    """Miniatura para avatares (140px de alto)."""
    filename = PHOTO_INDEX.get(name or "")
    if filename:
        return f"/static/photos/{filename}"
    return (remote_photo_index().get(name or "") or {}).get("url")


def photo_url_lg(name: str) -> Optional[str]:
    """Retrato a resolución completa (450x550) para la ficha."""
    filename = PHOTO_INDEX.get(name or "")
    if filename:
        return f"/static/photos/lg/{filename}"
    return (remote_photo_index().get(name or "") or {}).get("url")


def photo_credit(name: str) -> Optional[str]:
    """Autor y licencia del retrato, que Commons obliga a acreditar."""
    entry = remote_photo_index().get(name or "")
    if not entry or not entry.get("license"):
        return None
    author = entry.get("author") or "Wikimedia Commons"
    return f"{author} · {entry['license']}"


@lru_cache(maxsize=None)
def _static_fingerprint(filename: str) -> str:
    path = STATIC_DIR / filename
    if not path.exists():
        return "0"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def static_url(filename: str) -> str:
    """Añade a la URL una huella del contenido del fichero.

    Sin esto el navegador reutiliza la hoja de estilos que ya tenía guardada, y
    una plantilla nueva se dibuja con el CSS viejo: los bloques que aún no
    existen en esa hoja aparecen sin estilo.

    La huella es del contenido, no de la fecha: Vercel despliega todos los
    ficheros con la misma fecha (octubre de 2018), así que `?v=1540000000` no
    cambiaba nunca y cada despliegue se veía con el CSS del anterior. Se
    calcula una vez por proceso, que es lo que dura un despliegue.
    """
    return f"/static/{filename}?v={_static_fingerprint(filename)}"


templates.env.globals["static_url"] = static_url
templates.env.filters["trade_side"] = trade_side
templates.env.filters["trade_kind"] = trade_kind
templates.env.filters["bracket_label"] = bracket_label
templates.env.filters["accent_slot"] = accent_slot
templates.env.filters["disclosure_lag"] = disclosure_lag
templates.env.filters["lag_flag"] = lag_flag
templates.env.filters["short_money"] = short_money
templates.env.filters["photo_url"] = photo_url
templates.env.filters["photo_url_lg"] = photo_url_lg
templates.env.filters["photo_credit"] = photo_credit

LANG_COOKIE = "twf_lang"


def resolve_lang(request: Request, lang: Optional[str]) -> str:
    """El parámetro `?lang=` manda; si no, la cookie; si no, español."""
    if lang:
        return normalise_lang(lang)
    return normalise_lang(request.cookies.get(LANG_COOKIE, DEFAULT_LANG))


def scope_url(request: Request, category: str) -> str:
    """Enlace de una pestaña de perfil, conservando búsqueda y filtros."""
    raw_query = request.scope.get("query_string", b"") or b""
    if isinstance(raw_query, bytes):
        raw_query = raw_query.decode("utf-8", "ignore")
    # El partido sólo existe en el Congreso: llevarlo a la pestaña de empresa
    # dejaba la lista vacía sin que se viera por qué.
    dropped = {"category", "party"} if category == "business" else {"category"}
    params = [(key, value) for key, value in parse_qsl(raw_query) if key not in dropped]
    if category:
        params.append(("category", category))
    return ("/?" + urlencode(params) if params else "/") + "#perfiles"


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
        # Lo pone el middleware. Sin él, la política de seguridad de contenido
        # descarta los scripts en línea de las plantillas.
        "csp_nonce": getattr(request.state, "csp_nonce", ""),
    }
    # La petición va primero: la firma antigua está deprecada en Starlette.
    response = templates.TemplateResponse(request, template, context)
    response.set_cookie(LANG_COOKIE, lang, max_age=60 * 60 * 24 * 365, samesite="lax")
    return response


# Lo que el dataset del Congreso deja en la columna de partido cuando no lo
# trae, más la etiqueta con la que se marca a los directivos. Ninguno de los dos
# es un partido: como opción del filtro sólo ofrecerían una lista que no filtra.
PARTY_PLACEHOLDERS = {"Unknown", "Business", ""}


# Cuántas fichas-resumen caben en la portada. Cada una lleva sus posiciones,
# su sesgo y su última operación, así que el número no es sólo cuestión de
# maquetación: multiplica lo que hay que agregar en la base.
DIGEST_PAGE_SIZE = 24

# Operaciones que caben en el panel del hero sin que crezca más que el titular.
HERO_FEED_SIZE = 5
# Cuántas operaciones recientes se repasan para encontrar cinco personas
# distintas. Un Form 4 de venta escalonada trae decenas de líneas.
HERO_FEED_WINDOW = 200

# Posiciones que se pintan dentro de una ficha. Cuatro caben sin que la tarjeta
# crezca, y bastan para leer de un vistazo dónde está concentrado el dinero.
DIGEST_POSITIONS = 4


def attach_digests(db: Session, people: list[dict[str, Any]], scoped_ids) -> None:
    """Rellena cada persona con el resumen que se pinta en su ficha.

    Tres consultas para toda la portada, no tres por persona: las posiciones
    principales, el reparto entre compras y ventas y la última operación
    declarada. Todo dentro del mismo filtro que ya acotó la búsqueda, para que
    la ficha no cuente operaciones que la portada no está mostrando.
    """
    if not people:
        return

    by_id = {person["id"]: person for person in people}
    ids = list(by_id)
    for person in people:
        person["positions"] = []
        person["sides"] = {"buy": 0, "sell": 0, "other": 0}
        person["buy_share"] = None
        person["last_trade"] = None

    # --- Dónde concentra su volumen -------------------------------------
    # Sólo compras y ventas: es el mismo volumen que ordena la portada, y una
    # concesión de acciones no dice nada de dónde decide meter su dinero.
    position_rows = db.execute(
        select(
            Trade.politician_id,
            Ticker.symbol,
            func.count(Trade.id),
            func.coalesce(func.sum(Trade.amount), 0.0),
        )
        .select_from(Trade)
        .join(scoped_ids, scoped_ids.c.id == Trade.id)
        .join(Ticker, Ticker.id == Trade.ticker_id)
        .where(Trade.politician_id.in_(ids), OPEN_MARKET)
        .group_by(Trade.politician_id, Ticker.symbol)
    ).all()

    grouped: dict[int, list[dict[str, Any]]] = {}
    for politician_id, symbol, operations, volume in position_rows:
        grouped.setdefault(politician_id, []).append(
            {"symbol": symbol, "operations": operations, "volume": float(volume)}
        )

    for politician_id, entries in grouped.items():
        entries.sort(key=lambda item: item["volume"], reverse=True)
        top = entries[:DIGEST_POSITIONS]
        # La cuota es sobre el volumen declarado de esa persona, no sobre su
        # mayor valor: así el número se lee solo ("el 92% de lo que compra y
        # vende es un único valor") en vez de necesitar la barra de al lado.
        declared = by_id[politician_id]["volume"]
        for entry in top:
            # Sin redondear: la plantilla distingue "<1%" de un 0% de verdad, y
            # con un decimal un 0,04% ya llegaba como cero.
            entry["share"] = entry["volume"] / declared * 100 if declared else 0.0
        by_id[politician_id]["positions"] = top
        by_id[politician_id]["other_positions"] = max(len(entries) - len(top), 0)

    # --- Sesgo comprador o vendedor --------------------------------------
    side_rows = db.execute(
        select(Trade.politician_id, Trade.trade_type, func.count(Trade.id))
        .select_from(Trade)
        .join(scoped_ids, scoped_ids.c.id == Trade.id)
        .where(Trade.politician_id.in_(ids))
        .group_by(Trade.politician_id, Trade.trade_type)
    ).all()

    for politician_id, trade_type, count in side_rows:
        by_id[politician_id]["sides"][trade_side(trade_type)] += count

    for person in people:
        sides = person["sides"]
        # Las operaciones sin clasificar quedan fuera del porcentaje: no son
        # ni compra ni venta, y meterlas en el denominador diluiría el sesgo.
        classified = sides["buy"] + sides["sell"]
        if classified:
            person["buy_share"] = round(sides["buy"] / classified * 100)

    # --- Última compra o venta declarada ----------------------------------
    # Una función de ventana en lugar de una consulta por persona: numera las
    # operaciones de cada una por fecha y se queda con la primera de cada grupo.
    # Las concesiones y retenciones quedan fuera: la última decisión de
    # inversión es la señal, no la última nómina en acciones.
    ranked = (
        select(
            Trade.politician_id.label("politician_id"),
            Ticker.symbol.label("symbol"),
            Trade.trade_type.label("trade_type"),
            Trade.reported_date.label("reported_date"),
            Trade.amount.label("amount"),
            func.row_number()
            .over(
                partition_by=Trade.politician_id,
                order_by=(Trade.reported_date.desc(), Trade.id.desc()),
            )
            .label("position"),
        )
        .select_from(Trade)
        .join(scoped_ids, scoped_ids.c.id == Trade.id)
        .join(Ticker, Ticker.id == Trade.ticker_id)
        .where(Trade.politician_id.in_(ids), OPEN_MARKET)
        .subquery()
    )
    for row in db.execute(select(ranked).where(ranked.c.position == 1)).all():
        by_id[row.politician_id]["last_trade"] = {
            "symbol": row.symbol,
            "trade_type": row.trade_type,
            "date": row.reported_date,
            "amount": float(row.amount),
        }


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
    # Los directivos no tienen partido: en su pestaña el filtro se ignora en
    # vez de dejar la lista vacía.
    if category == "business":
        party = None

    scope_filters = []
    if chamber:
        scope_filters.append(Politician.chamber == chamber)
    if party:
        scope_filters.append(Politician.party == party)
    if category in ("congress", "business"):
        scope_filters.append(Politician.category == category)

    trade_query = select(Trade).join(Trade.politician).join(Trade.ticker).where(published())
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

    # El panel del hero enseña una compra o venta por persona. Un mismo filing
    # trae decenas de líneas seguidas —un directivo vendiendo por tramos—, así
    # que las doce operaciones de abajo no dan para cinco nombres: en
    # producción el panel abría con cuatro veces el mismo. Se mira más atrás.
    hero_candidates = db.scalars(
        trade_query.where(OPEN_MARKET, Trade.amount > 0)
        .order_by(Trade.reported_date.desc(), Trade.id.desc())
        .limit(HERO_FEED_WINDOW)
    ).all()
    hero_trades: list[Trade] = []
    seen_people: set[int] = set()
    for trade in hero_candidates:
        if trade.politician_id in seen_people:
            continue
        seen_people.add(trade.politician_id)
        hero_trades.append(trade)
        if len(hero_trades) == HERO_FEED_SIZE:
            break
    # Si en lo reciente sólo hay un declarante, mejor repetir nombre que
    # dejar el panel a medias.
    if len(hero_trades) < HERO_FEED_SIZE:
        chosen = {id(trade) for trade in hero_trades}
        hero_trades += [
            trade for trade in hero_candidates if id(trade) not in chosen
        ][: HERO_FEED_SIZE - len(hero_trades)]

    # Agregados sobre el mismo filtro, calculados en SQL para no traer 30k filas.
    scoped_ids = trade_query.with_only_columns(Trade.id).subquery()
    totals_query = (
        select(
            func.count(Trade.id),
            OPEN_MARKET_VOLUME,
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
        # Compras y ventas: las concesiones periódicas de acciones a un
        # directivo inflaban el recuento de su propia empresa.
        .where(OPEN_MARKET)
        .group_by(Ticker.symbol)
        .order_by(func.count(Trade.id).desc())
        .limit(6)
    ).all()

    # Una fila por persona con su conteo y su volumen, resueltas en una sola
    # consulta agregada. El orden es por volumen de compras y ventas: es lo que
    # responde a "en qué mueve su dinero", mientras que contar operaciones sólo
    # premia a quien opera mucho aunque mueva calderilla.
    politician_query = (
        select(
            Politician,
            func.count(Trade.id).label("operations"),
            OPEN_MARKET_VOLUME.label("volume"),
        )
        .select_from(Trade)
        .join(scoped_ids, scoped_ids.c.id == Trade.id)
        .join(Politician, Politician.id == Trade.politician_id)
        .group_by(Politician.id)
        .order_by(OPEN_MARKET_VOLUME.desc(), func.count(Trade.id).desc())
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
    visible_politicians = politicians[:DIGEST_PAGE_SIZE]
    attach_digests(db, visible_politicians, scoped_ids)

    # Las opciones de cada desplegable, las de la pestaña activa: en la del
    # Congreso no pintan nada los cargos de empresa.
    category_filter = [Politician.category == category] if category in ("congress", "business") else []
    unique_chambers = db.scalars(
        select(Politician.chamber).where(*category_filter).distinct().order_by(Politician.chamber)
    ).all()
    unique_parties = db.scalars(
        select(Politician.party).where(*category_filter).distinct().order_by(Politician.party)
    ).all()

    return render(
        request,
        "index.html",
        {
            "politicians": visible_politicians,
            "hidden_politicians": max(len(politicians) - len(visible_politicians), 0),
            "recent_trades": recent_trades,
            "hero_trades": hero_trades,
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
            "parties": [
                value for value in unique_parties if value not in PARTY_PLACEHOLDERS
            ],
            "scope_url": lambda value: scope_url(request, value),
        },
        resolve_lang(request, lang),
    )


# El enlace a la API está en el pie de todas las páginas: sin tope, cada visita
# curiosa se lleva la tabla entera de operaciones en un solo JSON.
API_PAGE_SIZE = 100
API_MAX_PAGE_SIZE = 500


def amount_range(trade: Trade, category: str) -> Optional[list[Optional[int]]]:
    """Tramo declarado de una operación del Congreso, para la API.

    `amount` es el punto medio del tramo —lo que permite sumar—, y sin los
    límites al lado quien consuma la API lo leería como una cifra exacta.
    """
    if category != "congress":
        return None
    bracket = bracket_for(trade.amount)
    return list(bracket) if bracket else None


class TradeFilters:
    """Criterios de búsqueda de operaciones, comunes a la API, al CSV y al feed.

    Lo que pedía quien quiere usar los datos para algo: "compras de más de
    $50K en los últimos siete días", las de un valor o las de una persona.
    """

    def __init__(
        self,
        side: Optional[str] = None,
        ticker: Optional[str] = None,
        politician_id: Optional[int] = None,
        category: Optional[str] = None,
        min_amount: Optional[float] = None,
        since_days: Optional[int] = None,
    ):
        self.side = side
        self.ticker = ticker.strip().upper() if ticker else None
        self.politician_id = politician_id
        self.category = category
        self.min_amount = min_amount
        self.since_days = since_days

    @classmethod
    def of(cls, value: Any) -> "TradeFilters":
        # Llamada la ruta desde Python —las pruebas lo hacen— el parámetro
        # llega con el `Depends` por defecto en vez de con filtros.
        return value if isinstance(value, cls) else cls()

    def apply(self, query):
        query = query.where(published())
        trade_type = func.lower(Trade.trade_type)
        if self.side == "buy":
            query = query.where(trade_type.in_(BUY_TYPES))
        elif self.side == "sell":
            query = query.where(or_(trade_type.in_(SELL_TYPES), trade_type.like("sale%")))
        if self.ticker:
            query = query.where(Trade.ticker.has(Ticker.symbol == self.ticker))
        if self.politician_id:
            query = query.where(Trade.politician_id == self.politician_id)
        if self.category:
            query = query.where(Trade.politician.has(Politician.category == self.category))
        if self.min_amount is not None:
            query = query.where(Trade.amount >= self.min_amount)
        if self.since_days:
            query = query.where(Trade.reported_date >= date.today() - timedelta(days=self.since_days))
        return query


def trade_filters(
    side: Optional[str] = Query(None, pattern="^(buy|sell)$", description="buy o sell"),
    ticker: Optional[str] = Query(None, max_length=20),
    politician_id: Optional[int] = Query(None, ge=1),
    category: Optional[str] = Query(None, pattern="^(congress|business)$"),
    min_amount: Optional[float] = Query(None, ge=0, description="Importe mínimo en USD"),
    since_days: Optional[int] = Query(None, ge=1, le=3650, description="Publicadas en los últimos N días"),
) -> TradeFilters:
    return TradeFilters(side, ticker, politician_id, category, min_amount, since_days)


def trade_record(trade: Trade) -> dict[str, Any]:
    """Una operación tal como la publican la API, el CSV y el feed."""
    return {
        "id": trade.id,
        "politician_id": trade.politician_id,
        "politician": trade.politician.name,
        "category": trade.politician.category,
        "chamber": trade.politician.chamber,
        "ticker": trade.ticker.symbol,
        "trade_type": trade.trade_type,
        "side": trade_side(trade.trade_type),
        "amount": float(trade.amount),
        "amount_range": amount_range(trade, trade.politician.category),
        "reported_date": trade.reported_date.isoformat(),
        "transaction_date": (
            trade.transaction_date.isoformat() if trade.transaction_date else None
        ),
        # Días entre la operación y su publicación: el retraso que marca la ley.
        "disclosure_lag_days": disclosure_lag(trade),
        # Fuera del plazo de 45 días de la STOCK Act, o con un retraso tan
        # grande que lo probable es una fecha mal escrita en el filing.
        "late_filing": lag_flag(trade) == "late",
        "date_suspect": lag_flag(trade) == "suspect",
        # Cuándo la leyó esta web: el retraso que es cosa nuestra.
        "ingested_at": trade.ingested_at.isoformat() if trade.ingested_at else None,
    }


def filtered_trades(db: Session, filters: TradeFilters, limit: int, offset: int = 0):
    filters = TradeFilters.of(filters)
    query = filters.apply(
        select(Trade).options(joinedload(Trade.politician), joinedload(Trade.ticker))
    )
    return db.scalars(
        query.order_by(Trade.reported_date.desc(), Trade.id.desc()).limit(limit).offset(offset)
    ).all()


@app.get("/api/trades")
def get_trades(
    db: Session = Depends(get_db),
    limit: int = Query(API_PAGE_SIZE, ge=1, le=API_MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
    filters: TradeFilters = Depends(trade_filters),
) -> dict[str, Any]:
    filters = TradeFilters.of(filters)
    total = db.scalar(filters.apply(select(func.count(Trade.id)))) or 0
    # Con joinedload: sin él, pintar cien operaciones son doscientas consultas
    # más, una por el político y otra por el valor de cada una.
    trades = filtered_trades(db, filters, limit, offset)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": [trade_record(trade) for trade in trades],
    }


# El CSV sale entero, sin tope: es la exportación para analizar los datos
# fuera, y con 1.000 filas por defecto (5.000 como mucho) se quedaban fuera
# veinte mil operaciones. Se escribe por tandas mientras se envía, así que la
# tabla completa no pasa entera por memoria.
CSV_BATCH_ROWS = 1000
CSV_COLUMNS = (
    "id", "reported_date", "transaction_date", "disclosure_lag_days", "late_filing",
    "date_suspect", "politician", "category", "chamber", "ticker", "side", "trade_type",
    "amount", "amount_min", "amount_max", "ingested_at",
)


def csv_chunks(bind, filters: TradeFilters, limit: Optional[int] = None, offset: int = 0):
    """Las filas del CSV en trozos de texto, leyendo la base por tandas.

    Con su propia sesión sobre el mismo motor: la de la petición se cierra al
    salir de la ruta, antes de que termine de enviarse la respuesta.
    """
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    yield buffer.getvalue()

    sent = 0
    with Session(bind=bind) as db:
        while limit is None or sent < limit:
            size = CSV_BATCH_ROWS if limit is None else min(CSV_BATCH_ROWS, limit - sent)
            trades = filtered_trades(db, filters, size, offset + sent)
            if not trades:
                break
            buffer.seek(0)
            buffer.truncate()
            for trade in trades:
                record = trade_record(trade)
                bracket = record["amount_range"] or [None, None]
                record["amount_min"], record["amount_max"] = bracket
                writer.writerow(
                    ["" if record[column] is None else record[column] for column in CSV_COLUMNS]
                )
            yield buffer.getvalue()
            sent += len(trades)
            # Lo ya escrito no hace falta en la sesión: así no crece con la tabla.
            db.expunge_all()


@app.get("/api/trades.csv")
def export_trades_csv(
    db: Session = Depends(get_db),
    limit: Optional[int] = Query(None, ge=1, description="Sin límite: todas las operaciones"),
    offset: int = Query(0, ge=0),
    filters: TradeFilters = Depends(trade_filters),
) -> Response:
    """Las mismas operaciones y filtros que /api/trades, en CSV y completas."""
    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        csv_chunks(db.get_bind(), TradeFilters.of(filters), limit, offset),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="thewhalefiles-trades.csv"'},
    )


FEED_SIZE = 50


@app.get("/feed.xml")
def trades_feed(
    request: Request,
    db: Session = Depends(get_db),
    filters: TradeFilters = Depends(trade_filters),
) -> Response:
    """Feed Atom de las últimas operaciones publicadas, con los filtros de la API.

    Es el aviso de operaciones nuevas que admite una web sin cuentas: cualquier
    lector de feeds, o un servicio que convierta feeds en correos o mensajes,
    avisa en cuanto el refresco programado las ingiere.
    """
    from xml.sax.saxutils import escape

    base = site_base_url(request)
    trades = filtered_trades(db, filters, FEED_SIZE)
    updated = (
        max((trade.ingested_at or datetime.combine(trade.reported_date, datetime.min.time())) for trade in trades)
        if trades
        else utcnow()
    )
    entries = []
    for trade in trades:
        record = trade_record(trade)
        bracket = bracket_label(trade.amount) if record["category"] == "congress" else None
        amount = bracket or compact_money(record["amount"])
        title = f"{record['politician']}: {record['trade_type']} {record['ticker']} ({amount})"
        summary = f"Publicada {record['reported_date']}, operación {record['transaction_date'] or '—'}."
        entries.append(
            "<entry>"
            f"<id>{escape(base)}/trades/{trade.id}</id>"
            f"<title>{escape(title)}</title>"
            f'<link href="{escape(base)}/politicians/{trade.politician_id}"/>'
            f"<updated>{record['reported_date']}T00:00:00Z</updated>"
            f"<summary>{escape(summary)}</summary>"
            "</entry>"
        )
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        "<title>TheWhaleFiles · operaciones declaradas</title>"
        f"<id>{escape(base)}/feed.xml</id>"
        f'<link rel="self" href="{escape(base)}/feed.xml"/>'
        f"<updated>{updated.strftime('%Y-%m-%dT%H:%M:%SZ')}</updated>"
        + "".join(entries)
        + "</feed>"
    )
    return Response(content=xml, media_type="application/atom+xml")


@app.get("/api/politicians")
def get_politicians(
    db: Session = Depends(get_db),
    limit: int = Query(API_PAGE_SIZE, ge=1, le=API_MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    total = db.scalar(select(func.count(Politician.id))) or 0
    # El recuento va agregado en la propia consulta. Con `len(politician.trades)`
    # cada fila del listado disparaba su consulta para acabar contando filas.
    rows = db.execute(
        select(Politician, func.count(Trade.id).label("trade_count"))
        .outerjoin(Trade, Trade.politician_id == Politician.id)
        .group_by(Politician.id)
        .order_by(Politician.id)
        .limit(limit)
        .offset(offset)
    ).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": [
            {
                "id": politician.id,
                "name": politician.name,
                "chamber": politician.chamber,
                "state": politician.state,
                "party": politician.party,
                "trade_count": trade_count,
            }
            for politician, trade_count in rows
        ],
    }


def performance_for_api(performance: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if performance is None:
        return None
    computed_at = performance.get("computed_at")
    return {
        **performance,
        "computed_at": computed_at.isoformat() if computed_at else None,
    }


@app.get("/api/politicians/{politician_id}")
def get_politician_detail(
    politician_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(API_PAGE_SIZE, ge=1, le=API_MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    politician = db.get(Politician, politician_id)
    if not politician:
        raise HTTPException(status_code=404, detail="Politician not found")

    trades = db.scalars(
        select(Trade)
        .options(joinedload(Trade.ticker))
        .where(Trade.politician_id == politician_id, published())
        .order_by(Trade.reported_date.desc(), Trade.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    total = db.scalar(
        select(func.count(Trade.id)).where(Trade.politician_id == politician_id, published())
    ) or 0

    return {
        "id": politician.id,
        "name": politician.name,
        "chamber": politician.chamber,
        "state": politician.state,
        "party": politician.party,
        "total_trades": total,
        # Rentabilidad de copiar sus operaciones frente al índice, si hay datos
        # para calcularla: la misma que enseña la ficha.
        "performance": performance_for_api(load_performance(db, politician_id)),
        "limit": limit,
        "offset": offset,
        "trades": [
            {
                "id": trade.id,
                "ticker": trade.ticker.symbol,
                "trade_type": trade.trade_type,
                "amount": float(trade.amount),
                "amount_range": amount_range(trade, politician.category),
                "reported_date": trade.reported_date.isoformat(),
                "transaction_date": (
                    trade.transaction_date.isoformat() if trade.transaction_date else None
                ),
                "disclosure_lag_days": disclosure_lag(trade),
                "late_filing": lag_flag(trade) == "late",
                "date_suspect": lag_flag(trade) == "suspect",
            }
            for trade in trades
        ],
    }


DORMANT_AFTER_DAYS = 365


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

    # El id desempata: un mismo filing trae varias líneas con la misma fecha y,
    # sin él, su orden cambiaba de una visita a otra.
    today = date.today()
    ordered_trades = sorted(
        (trade for trade in politician.trades if trade.reported_date <= today),
        key=lambda trade: (trade.reported_date, trade.id),
        reverse=True,
    )

    # Volumen y valores más operados, sólo con compras y ventas: la misma
    # cuenta que la portada, para que la ficha no diga otra cifra.
    total_amount = 0.0
    side_counts = {"buy": 0, "sell": 0, "other": 0}
    # El reparto por importe al lado del recuento: 25 compras frente a 51
    # ventas no dice si se compró o se vendió más dinero. Lo que no es de
    # mercado se suma aparte para decir cuánto se ha dejado fuera del volumen.
    side_volume = {"buy": 0.0, "sell": 0.0, "other": 0.0}
    ticker_volume: dict[str, dict[str, Any]] = {}
    for trade in ordered_trades:
        side = trade_side(trade.trade_type)
        side_counts[side] += 1
        side_volume[side] += float(trade.amount or 0)
        if side == "other":
            continue
        total_amount += float(trade.amount)
        entry = ticker_volume.setdefault(
            trade.ticker.symbol, {"symbol": trade.ticker.symbol, "operations": 0, "volume": 0.0}
        )
        entry["operations"] += 1
        entry["volume"] += float(trade.amount)

    # Ordenado por capital, no por número de operaciones: en una ficha con
    # una operación por valor, contar operaciones no distingue nada.
    top_tickers = sorted(ticker_volume.values(), key=lambda item: item["volume"], reverse=True)[:5]

    # Los tramos del Congreso se suman por su punto medio; al lado va la
    # horquilla de verdad, la suma de sus límites.
    declared_range = None
    if politician.category == "congress":
        declared_range = volume_range(
            trade.amount for trade in ordered_trades if trade_side(trade.trade_type) != "other"
        )

    # Cuánto tarda en declarar: días entre la operación y su publicación.
    lags = [lag for lag in (disclosure_lag(trade) for trade in ordered_trades) if lag is not None]
    # Las fechas inverosímiles se cuentan aparte: un "2015" que era 2025
    # convertía la media en años.
    plausible_lags = [lag for lag in lags if lag <= SUSPECT_LAG_DAYS]
    average_lag = round(sum(plausible_lags) / len(plausible_lags)) if plausible_lags else None
    visible_trades = ordered_trades[:60]
    resolved_lang = resolve_lang(request, lang)

    # La biografía es la de Wikipedia, no un resumen de sus inversiones. Si no
    # existe en el idioma activo se cae al otro antes de darse por vencido.
    bio = getattr(politician, f"bio_{resolved_lang}", None)
    bio_is_fallback = False
    if not bio:
        other = "en" if resolved_lang == "es" else "es"
        bio = getattr(politician, f"bio_{other}", None)
        bio_is_fallback = bool(bio)
    headline = getattr(politician, f"bio_headline_{resolved_lang}", None) or getattr(
        politician, "bio_headline_en", None
    )

    # Sólo los insiders corporativos declaran número de acciones (Form 4), así
    # que sólo ellos pueden tener patrimonio calculado.
    #
    # Con las cotizaciones que haya en caché, nunca pidiéndolas en la petición:
    # Yahoo responde 429 a menudo y cada valor sin precio esperaba hasta medio
    # minuto de reintentos. La ficha de Buffett tardaba tres minutos en abrir.
    # Las refresca el hilo de polling o `python -m app.prices`, y la ficha dice
    # siempre de cuándo son.
    # Un directivo que deja el cargo deja de presentar Form 4, y su ficha se
    # quedaría con cifras viejas presentadas como actuales. Pasado un año sin
    # declarar, la ficha lo dice.
    dormant_since = None
    if politician.category == "business" and ordered_trades:
        last_filing = ordered_trades[0].reported_date
        if (today - last_filing).days > DORMANT_AFTER_DAYS:
            dormant_since = last_filing

    performance = load_performance(db, politician.id)

    wealth = None
    derivatives = None
    if politician.category == "business" and politician.holdings:
        wealth = value_holdings(politician.holdings, refresh=False)
    if politician.category == "business" and politician.derivatives:
        derivatives = value_derivatives(politician.derivatives, refresh=False)

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
            "side_volume": side_volume,
            "top_tickers": top_tickers,
            "bio": bio,
            "bio_is_fallback": bio_is_fallback,
            "bio_headline": headline,
            "wealth": wealth,
            "derivatives": derivatives,
            "dormant_since": dormant_since,
            "declared_range": declared_range,
            "average_lag": average_lag,
            "late_filings": sum(1 for lag in plausible_lags if lag > LEGAL_DEADLINE_DAYS)
            if politician.category == "congress"
            else 0,
            "suspect_dates": len(lags) - len(plausible_lags),
            "performance": performance,
            "price_source": price_source(),
        },
        resolved_lang,
    )


@app.post("/api/load-sample-filing")
def load_sample_filing(request: Request) -> dict[str, Any]:
    """Carga el filing de ejemplo. Sólo para administración.

    Escribe en la base operaciones de un político inventado. Abierto al público
    convertía en editable la única cosa que esta web promete: que lo que se ve
    salió de una declaración oficial.
    """
    require_admin(request)

    sample_file = DATA_DIR / "sample_senate_filing.txt"
    if not sample_file.exists():
        raise HTTPException(status_code=404, detail="Sample filing not found")

    raw_text = sample_file.read_text(encoding="utf-8")
    imported_trades = load_filing_into_db(raw_text, "Alex Morgan")
    return {
        "politician": "Alex Morgan",
        "imported_count": len(imported_trades),
        "records": imported_trades,
    }


@app.get("/legal", response_class=HTMLResponse)
def legal_page(request: Request, lang: Optional[str] = None) -> Any:
    """Aviso legal, términos de uso y privacidad, en una sola página."""
    return render(request, "legal.html", {}, resolve_lang(request, lang))


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "TheWhaleFiles"}


# --- Indexación ------------------------------------------------------------

# La API no pinta nada en un buscador: lo que se indexa son las fichas y la
# portada.
ROBOTS_TXT = """User-agent: *
Disallow: /api/

Sitemap: {base}/sitemap.xml
"""


def site_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots(request: Request) -> str:
    return ROBOTS_TXT.format(base=site_base_url(request))


@app.get("/sitemap.xml")
def sitemap(request: Request, db: Session = Depends(get_db)) -> Any:
    base = site_base_url(request)
    # Sólo las fichas con operaciones: una ficha vacía no aporta nada a quien
    # llega desde un buscador.
    ids = db.scalars(
        select(Politician.id)
        .join(Trade, Trade.politician_id == Politician.id)
        .group_by(Politician.id)
        .order_by(Politician.id)
    ).all()

    urls = [f"{base}/", f"{base}/legal"] + [
        f"{base}/politicians/{person_id}" for person_id in ids
    ]
    body = "".join(f"<url><loc>{url}</loc></url>" for url in urls)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'
    return Response(content=xml, media_type="application/xml")


# --- Errores ---------------------------------------------------------------


def wants_json(request: Request) -> bool:
    path = request.url.path
    return path.startswith("/api/") or path in {"/health", "/sitemap.xml", "/feed.xml"}


def error_page(request: Request, status_code: int) -> Any:
    lang = resolve_lang(request, None)
    t = get_translations(lang)
    key = "error_404" if status_code == 404 else "error_generic"
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "request": request,
            "lang": lang,
            "other_lang": "en" if lang == "es" else "es",
            "lang_switch_url": lang_switch_url(request, "en" if lang == "es" else "es"),
            "t": t,
            "csp_nonce": getattr(request.state, "csp_nonce", ""),
            "status_code": status_code,
            "message": t[key],
        },
        status_code=status_code,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> Any:
    if wants_json(request):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    return error_page(request, exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> Any:
    # En la API, el 422 de siempre: dice qué parámetro sobra o falta. En una
    # página, "/politicians/abc" es una ficha que no existe, y enseñaba el JSON
    # del validador en lugar de la página de error.
    if wants_json(request):
        return await request_validation_exception_handler(request, exc)
    return error_page(request, 404)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> Any:
    # El detalle va al registro, no a la página: un traceback en pantalla dice
    # más de la casa que del problema.
    logger.exception("Error no controlado en %s", request.url.path)

    if wants_json(request):
        return JSONResponse({"detail": "Internal server error"}, status_code=500)
    return error_page(request, 500)


@app.post("/api/poll-sources")
def poll_sources_endpoint(request: Request) -> dict[str, Any]:
    """Fuerza una pasada de ingesta. Sólo para administración.

    Cada llamada sale a la red contra las fuentes oficiales y escribe en la
    base. Sin puerta, cualquiera podía usar el servidor como amplificador de
    peticiones contra la SEC y el House Clerk, y pagábamos nosotros la factura.
    """
    require_admin(request)

    imported = poll_official_sources()
    return {
        "imported_count": len(imported),
        "records": imported[:10],
    }
