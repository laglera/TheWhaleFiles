"""Cotizaciones de mercado para valorar las posiciones declaradas.

Hay dos proveedores. Por defecto se usa **Yahoo Finance**, que no pide registro
ni clave, de modo que la valoración funciona en cuanto se levanta el proyecto.
Si se configura `FINNHUB_API_KEY` se usa Finnhub, que da un dato más limpio
pero exige cuenta y tiene cuota.

En ambos casos las cotizaciones se cachean en la propia base: una ficha con
diez posiciones no puede gastar diez llamadas cada vez que alguien la abre.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from typing import Iterable, Optional

from sqlalchemy import select

from app.database import SessionLocal
from app.models import PriceQuote
from app.runtime import is_serverless, utcnow

logger = logging.getLogger(__name__)

# Yahoo limita por ráfaga y devuelve 429 con facilidad. Sus dos hosts llevan
# contadores separados, así que alternarlos absorbe la mayoría de los rechazos.
YAHOO_HOSTS = (
    "https://query1.finance.yahoo.com/v8/finance/chart/",
    "https://query2.finance.yahoo.com/v8/finance/chart/",
)
FINNHUB_URL = "https://finnhub.io/api/v1/quote"
# Yahoo rechaza las peticiones sin un User-Agent de navegador.
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
# Espaciado mínimo entre llamadas al proveedor, para no provocar el 429.
REQUEST_PAUSE = float(os.getenv("PRICE_REQUEST_PAUSE", "1.0"))
# Esperas crecientes cuando aun así rechaza. El límite de Yahoo no es una
# ráfaga puntual sino una ventana sostenida: con esperas cortas se encadenan
# los rechazos y una precarga entera se queda sin precios.
RETRY_BACKOFF = (3.0, 8.0, 20.0)

# Las cotizaciones se refrescan pasado este margen. Ningún proveedor gratuito da
# tiempo real estricto, y un cuarto de hora es irrelevante para valorar una
# posición declarada hace semanas.
CACHE_TTL = timedelta(minutes=int(os.getenv("PRICE_CACHE_MINUTES", "15")))


def api_key() -> Optional[str]:
    return os.getenv("FINNHUB_API_KEY") or None


def provider_name() -> str:
    return "Finnhub" if api_key() else "Yahoo Finance"


def normalise_symbol(symbol: str) -> str:
    """Adapta el símbolo del filing a la notación del proveedor.

    Los Formularios 4 escriben las clases de acción con punto o barra
    ("BRK.A", "LLYVA/K"); los proveedores usan guion o sólo la clase principal.
    """
    clean = (symbol or "").strip().upper()
    if "/" in clean:
        clean = clean.split("/")[0]
    return clean.replace(".", "-")


def _get_json(url: str, user_agent: str) -> Optional[dict]:
    time.sleep(REQUEST_PAUSE)
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise RateLimited(url) from error
        return None
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
        return None


class RateLimited(Exception):
    """El proveedor ha rechazado la petición por exceso de ráfaga."""


def fetch_from_yahoo(symbol: str) -> Optional[dict[str, object]]:
    quoted = urllib.parse.quote(normalise_symbol(symbol))
    payload = None
    # Se alternan los dos hosts y, si ambos rechazan, se espera cada vez más:
    # el límite de Yahoo es por ráfaga y se suelta en unos segundos.
    for round_index, wait in enumerate((0.0,) + RETRY_BACKOFF):
        if wait:
            time.sleep(wait)
        for host in YAHOO_HOSTS:
            try:
                payload = _get_json(f"{host}{quoted}?interval=1d&range=1d", BROWSER_UA)
            except RateLimited:
                continue
            break
        if payload is not None:
            break
    if not payload:
        return None

    results = (payload.get("chart") or {}).get("result") or []
    if not results:
        return None
    meta = results[0].get("meta") or {}

    price = meta.get("regularMarketPrice")
    if not price:
        return None
    return {
        "price": float(price),
        "previous_close": float(meta.get("chartPreviousClose") or meta.get("previousClose") or 0.0),
        "currency": meta.get("currency") or "USD",
        "name": meta.get("longName") or meta.get("shortName"),
    }


def fetch_from_finnhub(symbol: str) -> Optional[dict[str, object]]:
    key = api_key()
    if not key:
        return None

    url = (
        f"{FINNHUB_URL}?symbol={urllib.parse.quote(normalise_symbol(symbol))}"
        f"&token={urllib.parse.quote(key)}"
    )
    try:
        payload = _get_json(url, "TheWhaleFiles/0.1")
    except RateLimited:
        return None
    if not payload:
        return None

    price = payload.get("c")
    # Finnhub responde con c=0 para símbolos que no reconoce.
    if not price:
        return None
    return {
        "price": float(price),
        "previous_close": float(payload.get("pc") or 0.0),
        "currency": "USD",
        "name": None,
    }


def fetch_quote(symbol: str) -> Optional[dict[str, object]]:
    """Consulta el precio actual de un valor. `None` si no se puede obtener."""
    data = fetch_from_finnhub(symbol) if api_key() else None
    if data is None:
        data = fetch_from_yahoo(symbol)
    if data is None:
        logger.info("Sin cotización para %s", symbol)
    return data


def get_prices(symbols: Iterable[str], refresh: bool = True) -> dict[str, PriceQuote]:
    """Cotizaciones de varios valores, tirando de caché siempre que se pueda."""
    wanted = sorted({(symbol or "").strip().upper() for symbol in symbols if symbol})
    if not wanted:
        return {}

    # En serverless la petición web no puede pararse a hablar con el proveedor.
    # Yahoo responde 429 con facilidad y los reintentos esperan hasta medio
    # minuto por símbolo: una ficha con posiciones agotaría el tiempo de la
    # función y devolvería un error en vez de la página. Allí se sirve lo que
    # haya cacheado —la ficha muestra de cuándo es— y el refresco se hace
    # aparte, con `python -m app.prices` contra la base de producción.
    if refresh and is_serverless():
        refresh = False

    now = utcnow()
    quotes: dict[str, PriceQuote] = {}

    with SessionLocal() as db:
        cached = {
            quote.symbol: quote
            for quote in db.scalars(select(PriceQuote).where(PriceQuote.symbol.in_(wanted))).all()
        }

        for symbol in wanted:
            quote = cached.get(symbol)
            fresh_enough = quote is not None and (now - quote.fetched_at) < CACHE_TTL
            if fresh_enough or not refresh:
                if quote is not None:
                    quotes[symbol] = quote
                continue

            data = fetch_quote(symbol)
            if data is None:
                # Se conserva lo cacheado aunque esté caducado: un precio de
                # hace una hora informa más que un hueco en la tabla.
                if quote is not None:
                    quotes[symbol] = quote
                continue

            if quote is None:
                quote = PriceQuote(symbol=symbol)
                db.add(quote)
            quote.price = float(data["price"])
            quote.previous_close = float(data["previous_close"])
            quote.currency = str(data.get("currency") or "USD")
            quote.fetched_at = now
            quotes[symbol] = quote

        db.commit()
        # Los objetos se usan después de cerrar la sesión: se copian a un
        # contenedor suelto para que no queden expirados.
        return {
            symbol: PriceQuote(
                symbol=quote.symbol,
                price=quote.price,
                currency=quote.currency,
                previous_close=quote.previous_close,
                fetched_at=quote.fetched_at,
            )
            for symbol, quote in quotes.items()
        }


def value_holdings(holdings: list, refresh: bool = False) -> dict[str, object]:
    """Valora una lista de posiciones a precio de mercado.

    Por defecto sólo con lo cacheado: quien la llama suele ser una petición
    web, y esperar al proveedor ahí la deja colgada. Para refrescar, `refresh`.
    """
    symbols = [holding.ticker.symbol for holding in holdings]
    return combine_positions(holdings, get_prices(symbols, refresh=refresh))


def combine_positions(holdings: list, quotes: dict) -> dict[str, object]:
    """Cruza posiciones con cotizaciones.

    Las posiciones sin precio se marcan y quedan fuera del total: valorarlas a
    cero rebajaría el patrimonio, y omitirlas sin avisar lo daría por completo.
    """
    positions = []
    total = 0.0
    valued = 0
    for holding in holdings:
        symbol = holding.ticker.symbol
        quote = quotes.get(symbol)
        value = holding.shares * quote.price if quote else None
        if value is not None:
            total += value
            valued += 1
        change = None
        if quote and quote.previous_close:
            change = (quote.price - quote.previous_close) / quote.previous_close * 100

        positions.append(
            {
                "symbol": symbol,
                "name": holding.ticker.name,
                "shares": holding.shares,
                "as_of": holding.as_of,
                "price": quote.price if quote else None,
                "change_pct": change,
                "value": value,
            }
        )

    positions.sort(key=lambda item: (item["value"] is None, -(item["value"] or 0)))
    return {
        "positions": positions,
        "total": total,
        "valued": valued,
        "missing": len(positions) - valued,
        "fetched_at": max((quote.fetched_at for quote in quotes.values()), default=None),
    }


def warm_cache(verbose: bool = True) -> dict[str, int]:
    """Precarga la cotización de todo lo que hay en cartera.

    Pensado para ejecutarse a mano o desde un cron: deja la caché lista para
    que ninguna visita a una ficha tenga que esperar al proveedor.
    """
    from app.models import Holding, Ticker

    with SessionLocal() as db:
        symbols = [
            row[0]
            for row in db.execute(
                select(Ticker.symbol).join(Holding, Holding.ticker_id == Ticker.id).distinct()
            ).all()
        ]

    stats = {"symbols": len(symbols), "priced": 0, "failed": 0}
    failures = 0
    for symbol in symbols:
        # Tras varios rechazos seguidos se afloja el ritmo: seguir insistiendo
        # al mismo paso sólo alarga la ventana de bloqueo.
        if failures >= 3:
            time.sleep(15.0)
            failures = 0

        quotes = get_prices([symbol])
        if quotes:
            stats["priced"] += 1
            failures = 0
            if verbose:
                print(f"  ok {symbol:10s} {quotes[symbol].price:,.2f}", flush=True)
        else:
            stats["failed"] += 1
            failures += 1
            if verbose:
                print(f"  -- {symbol:10s} sin cotización", flush=True)
    return stats


def refresh_ticker_names(symbols: Optional[list[str]] = None) -> int:
    """Rellena el nombre real del emisor, que los filings no traen.

    La ingesta guarda el símbolo también como nombre, así que las tablas
    muestran "TSLA · TSLA" en vez de "TSLA · Tesla, Inc.".
    """
    from app.models import Ticker

    updated = 0
    with SessionLocal() as db:
        query = select(Ticker).where(Ticker.name == Ticker.symbol)
        if symbols:
            query = query.where(Ticker.symbol.in_(symbols))
        for ticker in db.scalars(query).all():
            data = fetch_from_yahoo(ticker.symbol)
            if data and data.get("name"):
                ticker.name = str(data["name"])
                updated += 1
        db.commit()
    return updated


if __name__ == "__main__":
    print(f"Precargando cotizaciones desde {provider_name()}...")
    print(warm_cache())
