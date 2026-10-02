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
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy import select

from app.database import SessionLocal
from app.models import PriceQuote
from app.money import ZERO, PRICE_SCALE, to_decimal
from app.runtime import is_serverless, utcnow

logger = logging.getLogger(__name__)

# Yahoo limita por ráfaga y devuelve 429 con facilidad. Sus dos hosts llevan
# contadores separados, así que alternarlos absorbe la mayoría de los rechazos.
YAHOO_HOSTS = (
    "https://query1.finance.yahoo.com/v8/finance/chart/",
    "https://query2.finance.yahoo.com/v8/finance/chart/",
)
FINNHUB_URL = "https://finnhub.io/api/v1/quote"
# Yahoo rechaza las peticiones sin un User-Agent de navegador, pero también
# las que imitan uno concreto: a la cadena completa de Chrome 124 contestaba
# 429 siempre, no por ráfaga, y ni el histórico del SPY ni las cotizaciones de
# las carteras se refrescaban (había precios de hace 39 días). La forma corta
# es la que acepta.
BROWSER_UA = os.getenv("YAHOO_USER_AGENT", "Mozilla/5.0")
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


# Divisa en la que se valora el patrimonio. Las posiciones que cotizan en otra
# se convierten al tipo de cambio del día; antes se sumaban como si todo
# fueran dólares.
BASE_CURRENCY = (os.getenv("WEALTH_CURRENCY") or "USD").strip().upper()

# Yahoo da algunas bolsas en la unidad menor: Londres en peniques ("GBp"),
# Johannesburgo en céntimos. Sin dividir, una acción de 4 libras valía 400.
MINOR_UNITS = {"GBP": ("GBP", 1), "GBp": ("GBP", 100), "GBX": ("GBP", 100),
               "ZAc": ("ZAR", 100), "ZAC": ("ZAR", 100), "ILA": ("ILS", 100)}

# Una cotización más vieja que esto se marca en la ficha: el refresco corre cada
# seis horas, así que pasado un día es que ha fallado y el valor ya no es el
# del mercado.
STALE_AFTER = timedelta(hours=float(os.getenv("PRICE_STALE_HOURS", "24")))


def normalise_currency(raw: Optional[str]) -> tuple[str, Decimal]:
    """Divisa ISO y divisor para pasar el precio a su unidad principal."""
    code = (raw or "USD").strip()
    if code in MINOR_UNITS:
        currency, divisor = MINOR_UNITS[code]
        return currency, Decimal(divisor)
    return code.upper(), Decimal(1)


def fx_symbol(currency: str, base: str = BASE_CURRENCY) -> str:
    """Par de divisas en la notación de Yahoo: EURUSD=X."""
    return f"{currency}{base}=X"


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
            # Los precios llegan como texto decimal y así se quedan: pasar por
            # float los convertiría en su aproximación binaria.
            return json.loads(response.read(), parse_float=Decimal)
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise RateLimited(url) from error
        return None
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
        return None


class RateLimited(Exception):
    """El proveedor ha rechazado la petición por exceso de ráfaga."""


def yahoo_chart(symbol: str, query: str = "interval=1d&range=1d") -> Optional[dict]:
    """Respuesta cruda del endpoint `chart` de Yahoo, con reintentos."""
    quoted = urllib.parse.quote(normalise_symbol(symbol))
    payload = None
    # Se alternan los dos hosts y, si ambos rechazan, se espera cada vez más:
    # el límite de Yahoo es por ráfaga y se suelta en unos segundos.
    for round_index, wait in enumerate((0.0,) + RETRY_BACKOFF):
        if wait:
            time.sleep(wait)
        for host in YAHOO_HOSTS:
            try:
                payload = _get_json(f"{host}{quoted}?{query}", BROWSER_UA)
            except RateLimited:
                continue
            break
        if payload is not None:
            break
    return payload or None


def fetch_from_yahoo(symbol: str) -> Optional[dict[str, object]]:
    payload = yahoo_chart(symbol)
    if not payload:
        return None

    results = (payload.get("chart") or {}).get("result") or []
    if not results:
        return None
    meta = results[0].get("meta") or {}

    price = meta.get("regularMarketPrice")
    if not price:
        return None
    currency, divisor = normalise_currency(meta.get("currency"))
    return {
        "price": to_decimal(price) / divisor,
        "previous_close": to_decimal(
            meta.get("chartPreviousClose") or meta.get("previousClose") or 0
        )
        / divisor,
        "currency": currency,
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
        "price": to_decimal(price),
        "previous_close": to_decimal(payload.get("pc") or 0),
        # El endpoint /quote no dice la divisa y en la cuota gratuita sólo
        # cubre la bolsa estadounidense. Un símbolo extranjero no llega aquí:
        # Finnhub responde c=0 y se cae a Yahoo, que sí la trae.
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
            quote.price = to_decimal(data["price"], PRICE_SCALE)
            quote.previous_close = to_decimal(data["previous_close"], PRICE_SCALE) or ZERO
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
    """Valora una lista de posiciones a precio de mercado, en la divisa base.

    Por defecto sólo con lo cacheado: quien la llama suele ser una petición
    web, y esperar al proveedor ahí la deja colgada. Para refrescar, `refresh`.
    """
    # Importado aquí: app.history usa este módulo para hablar con Yahoo.
    from app.history import load_actions

    symbols = [holding.ticker.symbol for holding in holdings]
    quotes = get_prices(symbols, refresh=refresh)
    with SessionLocal() as db:
        actions = load_actions(db, symbols)
    return combine_positions(
        holdings, quotes, exchange_rates(quotes.values(), refresh=refresh), actions=actions
    )


def value_derivatives(derivatives: list, refresh: bool = False) -> dict[str, object]:
    """Valora opciones, warrants y convertibles por su valor intrínseco."""
    symbols = [derivative.ticker.symbol for derivative in derivatives]
    quotes = get_prices(symbols, refresh=refresh)
    return combine_derivatives(derivatives, quotes, exchange_rates(quotes.values(), refresh=refresh))


def combine_derivatives(derivatives: list, quotes: dict, rates: Optional[dict] = None) -> dict[str, object]:
    """Valor intrínseco: lo que daría ejercer hoy, sin el valor temporal.

    (precio del subyacente − precio de ejercicio) × acciones del subyacente, o
    cero si el ejercicio cuesta más de lo que vale la acción. Una opción fuera
    del dinero sigue valiendo algo en el mercado —su valor temporal—, pero
    estimarlo exige un modelo y una volatilidad que los filings no dan: se
    prefiere quedarse corto y decirlo.
    """
    rates = rates or {}
    lines = []
    total = ZERO
    valued = 0
    for derivative in derivatives:
        symbol = derivative.ticker.symbol
        quote = quotes.get(symbol)
        rate = None
        if quote is not None:
            currency = quote.currency or "USD"
            if currency == BASE_CURRENCY:
                rate = Decimal(1)
            elif currency in rates:
                rate = to_decimal(rates[currency].price)
        strike = to_decimal(derivative.exercise_price) or ZERO
        value = None
        if quote is not None and rate:
            spread = max(to_decimal(quote.price) - strike, ZERO)
            value = to_decimal(derivative.underlying_shares) * spread * rate
            total += value
            valued += 1
        lines.append(
            {
                "symbol": symbol,
                "title": derivative.title,
                "underlying_shares": derivative.underlying_shares,
                "exercise_price": derivative.exercise_price,
                "expiration": derivative.expiration,
                "as_of": derivative.as_of,
                "price": quote.price if quote else None,
                "currency": quote.currency if quote else None,
                "in_the_money": value is not None and value > 0,
                "value": value,
            }
        )
    lines.sort(key=lambda item: (item["value"] is None, -(item["value"] or 0)))
    return {
        "positions": lines,
        "total": total,
        "currency": BASE_CURRENCY,
        "valued": valued,
        "missing": len(lines) - valued,
    }


def exchange_rates(quotes: Iterable, refresh: bool = False) -> dict[str, PriceQuote]:
    """Tipo de cambio a la divisa base de cada divisa que aparece en `quotes`."""
    currencies = sorted(
        {quote.currency for quote in quotes if quote.currency and quote.currency != BASE_CURRENCY}
    )
    if not currencies:
        return {}
    pairs = get_prices([fx_symbol(currency) for currency in currencies], refresh=refresh)
    return {
        currency: pairs[fx_symbol(currency)]
        for currency in currencies
        if fx_symbol(currency) in pairs
    }


def combine_positions(
    holdings: list,
    quotes: dict,
    rates: Optional[dict] = None,
    now=None,
    actions: Optional[dict] = None,
) -> dict[str, object]:
    """Cruza posiciones con cotizaciones, tipos de cambio y splits.

    Las posiciones sin precio —o en una divisa sin tipo de cambio— se marcan y
    quedan fuera del total: valorarlas a cero rebajaría el patrimonio, y
    omitirlas sin avisar lo daría por completo.

    Un split posterior a la fecha del saldo multiplica los títulos: el Form 4
    de antes del 10 por 1 de NVIDIA, contado tal cual, valía la décima parte.
    Los dividendos repartidos desde esa fecha se estiman aparte y no se suman
    al total: no se sabe si se reinvirtieron, se gastaron o tributaron.
    """
    from app.history import dividends_since, split_factor

    rates = rates or {}
    actions = actions or {}
    now = now or utcnow()
    positions = []
    # Títulos por precio en Decimal: con millones de acciones, el error de
    # redondeo de la coma flotante dejaba de ser despreciable.
    total = ZERO
    dividends_total = ZERO
    valued = 0
    used_quotes = []
    for holding in holdings:
        symbol = holding.ticker.symbol
        quote = quotes.get(symbol)
        symbol_actions = actions.get(symbol, [])
        factor = split_factor(symbol_actions, holding.as_of)
        shares_now = to_decimal(holding.shares) * factor
        currency = (quote.currency or "USD") if quote else None
        rate = None
        if quote is not None:
            used_quotes.append(quote)
            if currency == BASE_CURRENCY:
                rate = Decimal(1)
            elif currency in rates:
                rate = to_decimal(rates[currency].price)
                used_quotes.append(rates[currency])

        value = None
        dividends = None
        # De dónde sale cada dividendo: cuántos pagos y el último. Sin eso, un
        # "+X $" no distingue un yield sostenido de un reparto extraordinario.
        payouts = [
            action
            for action in symbol_actions
            if action.kind == "dividend" and action.day > holding.as_of and action.amount
        ]
        if quote is not None and rate:
            value = shares_now * to_decimal(quote.price) * rate
            total += value
            valued += 1
            per_share = dividends_since(symbol_actions, holding.as_of)
            if per_share:
                dividends = shares_now * per_share * rate
                dividends_total += dividends
        change = None
        if quote and quote.previous_close:
            change = float(
                (to_decimal(quote.price) - to_decimal(quote.previous_close))
                / to_decimal(quote.previous_close)
                * 100
            )

        positions.append(
            {
                "symbol": symbol,
                "name": holding.ticker.name,
                "shares": holding.shares,
                "shares_now": shares_now,
                "split_factor": factor,
                "dividends": dividends,
                "dividend_payments": len(payouts) if dividends else 0,
                "last_dividend": max((action.day for action in payouts), default=None) if dividends else None,
                # Precio de una cotización vieja: la fila se pinta apagada.
                "stale": bool(quote and quote.fetched_at and now - quote.fetched_at > STALE_AFTER),
                "shares_indirect": (getattr(holding, "shares_indirect", None) or ZERO) * factor,
                "as_of": holding.as_of,
                "price": quote.price if quote else None,
                "currency": currency,
                # Sin precio, o con precio pero sin tipo de cambio: son dos
                # huecos distintos y la ficha los explica por separado.
                "missing_reason": None if value is not None else ("fx" if quote else "quote"),
                "change_pct": change,
                "value": value,
            }
        )

    positions.sort(key=lambda item: (item["value"] is None, -(item["value"] or 0)))
    # La fecha que se enseña es la de la cotización más vieja que entra en la
    # cuenta: la más nueva daba por fresco un total hecho con precios de días.
    oldest = min((quote.fetched_at for quote in used_quotes), default=None)
    return {
        "positions": positions,
        "total": total,
        "currency": BASE_CURRENCY,
        "dividends": dividends_total,
        "split_adjusted": sum(1 for item in positions if item["split_factor"] != 1),
        "valued": valued,
        "missing": len(positions) - valued,
        "missing_fx": sum(1 for item in positions if item["missing_reason"] == "fx"),
        "converted": sum(
            1 for item in positions if item["value"] is not None and item["currency"] != BASE_CURRENCY
        ),
        "fetched_at": oldest,
        "stale": oldest is not None and now - oldest > STALE_AFTER,
        "stale_hours": int((now - oldest).total_seconds() // 3600) if oldest else None,
    }


def warm_cache(verbose: bool = True) -> dict[str, int]:
    """Precarga la cotización de todo lo que hay en cartera.

    Pensado para ejecutarse a mano o desde un cron: deja la caché lista para
    que ninguna visita a una ficha tenga que esperar al proveedor.
    """
    from app.models import DerivativeHolding, Holding, Ticker

    with SessionLocal() as db:
        symbols = sorted(
            {
                row[0]
                for model in (Holding, DerivativeHolding)
                for row in db.execute(
                    select(Ticker.symbol).join(model, model.ticker_id == Ticker.id).distinct()
                ).all()
            }
        )


    stats = {"symbols": len(symbols), "priced": 0, "failed": 0}
    _warm(symbols, stats, verbose)

    # Después, el tipo de cambio de cada divisa en la que cotiza algo de lo
    # anterior: sin él esas posiciones quedan fuera del total.
    with SessionLocal() as db:
        currencies = sorted(
            {
                row[0]
                for row in db.execute(
                    select(PriceQuote.currency).where(PriceQuote.symbol.in_(symbols)).distinct()
                ).all()
                if row[0] and row[0] != BASE_CURRENCY
            }
        )
    pairs = [fx_symbol(currency) for currency in currencies]
    stats["symbols"] += len(pairs)
    _warm(pairs, stats, verbose)
    return stats


def _warm(symbols: list[str], stats: dict[str, int], verbose: bool) -> None:
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
