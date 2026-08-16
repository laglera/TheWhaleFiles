"""Cotizaciones de mercado para valorar las posiciones declaradas.

Proveedor: Finnhub (`FINNHUB_API_KEY`). El plan gratuito da 60 peticiones por
minuto, así que las cotizaciones se cachean en la propia base: una ficha con
diez posiciones no puede gastar diez llamadas cada vez que alguien la abre.

Sin API key configurada el módulo no falla: devuelve vacío y la interfaz
muestra las posiciones sin valorar.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy import select

from app.database import SessionLocal
from app.models import PriceQuote

logger = logging.getLogger(__name__)

FINNHUB_URL = "https://finnhub.io/api/v1/quote"
# Las cotizaciones se refrescan pasado este margen. Con el plan gratuito no hay
# tiempo real estricto, y un minuto de antigüedad es irrelevante para valorar
# una posición declarada hace semanas.
CACHE_TTL = timedelta(minutes=int(os.getenv("PRICE_CACHE_MINUTES", "15")))


def api_key() -> Optional[str]:
    return os.getenv("FINNHUB_API_KEY") or None


def fetch_quote(symbol: str) -> Optional[dict[str, float]]:
    """Consulta el precio actual de un valor. `None` si no se puede obtener."""
    key = api_key()
    if not key:
        return None

    url = f"{FINNHUB_URL}?symbol={urllib.parse.quote(symbol)}&token={urllib.parse.quote(key)}"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "TheWhaleFiles/0.1"})
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        logger.warning("No se pudo consultar la cotización de %s", symbol)
        return None

    price = payload.get("c")
    # Finnhub responde con c=0 para símbolos que no cotizan o que no reconoce.
    if not price:
        return None
    return {"price": float(price), "previous_close": float(payload.get("pc") or 0.0)}


def get_prices(symbols: Iterable[str], refresh: bool = True) -> dict[str, PriceQuote]:
    """Cotizaciones de varios valores, tirando de caché siempre que se pueda."""
    wanted = sorted({(symbol or "").strip().upper() for symbol in symbols if symbol})
    if not wanted:
        return {}

    now = datetime.utcnow()
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
            quote.price = data["price"]
            quote.previous_close = data["previous_close"]
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


def value_holdings(holdings: list, refresh: bool = True) -> dict[str, object]:
    """Valora una lista de posiciones a precio de mercado."""
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
        "fetched_at": max(
            (quote.fetched_at for quote in quotes.values()), default=None
        ),
    }
