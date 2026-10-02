"""Ingesta de operaciones de directivos y grandes accionistas (SEC Form 4).

El equivalente empresarial del PTR del Congreso: la SEC obliga a directivos,
consejeros y accionistas de más del 10% a declarar sus operaciones en un
Formulario 4 dentro de los dos días hábiles siguientes.

Fuente: EDGAR (dominio público). La SEC exige un User-Agent identificable y
limita a 10 peticiones por segundo.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from app.database import SessionLocal, prepare_database
from app.models import DerivativeHolding, Holding, Politician, Ticker, Trade
from app.money import ZERO, money, to_decimal

USER_AGENT = "TheWhaleFiles/0.1 (contacto: alejandro.web00@gmail.com)"
REQUEST_PAUSE = 0.2  # ~5 peticiones por segundo, por debajo del límite de la SEC

# Figuras influyentes de la economía estadounidense, con su CIK personal en EDGAR.
INSIDERS: list[dict[str, str]] = [
    {"cik": "0001494730", "name": "Elon Musk", "role": "CEO", "org": "Tesla"},
    {"cik": "0001043298", "name": "Jeff Bezos", "role": "Fundador", "org": "Amazon"},
    {"cik": "0001214156", "name": "Tim Cook", "role": "CEO", "org": "Apple"},
    {"cik": "0000315090", "name": "Warren Buffett", "role": "CEO", "org": "Berkshire Hathaway"},
    {"cik": "0001548760", "name": "Mark Zuckerberg", "role": "CEO", "org": "Meta"},
    {"cik": "0001197649", "name": "Jensen Huang", "role": "CEO", "org": "NVIDIA"},
    {"cik": "0001513142", "name": "Satya Nadella", "role": "CEO", "org": "Microsoft"},
    {"cik": "0001534753", "name": "Sundar Pichai", "role": "CEO", "org": "Alphabet"},
    {"cik": "0001195345", "name": "Jamie Dimon", "role": "CEO", "org": "JPMorgan Chase"},
    {"cik": "0001059245", "name": "Larry Fink", "role": "CEO", "org": "BlackRock"},
    {"cik": "0001033331", "name": "Reed Hastings", "role": "Presidente", "org": "Netflix"},
    {"cik": "0000908724", "name": "Michael Dell", "role": "CEO", "org": "Dell Technologies"},
    {"cik": "0001205005", "name": "Safra Catz", "role": "CEO", "org": "Oracle"},
    {"cik": "0001374545", "name": "Andy Jassy", "role": "CEO", "org": "Amazon"},
    # Lisa T. Su. El CIK anterior (0001227903) era el de otra Lisa Su, con
    # operaciones de Travelzoo entre 2004 y 2021.
    {"cik": "0001405109", "name": "Lisa Su", "role": "CEO", "org": "AMD"},
    {"cik": "0001834152", "name": "Brian Chesky", "role": "CEO", "org": "Airbnb"},
    {"cik": "0001294693", "name": "Marc Benioff", "role": "CEO", "org": "Salesforce"},
    {"cik": "0000901999", "name": "Larry Ellison", "role": "Presidente", "org": "Oracle"},
    # David M. Solomon. El CIK anterior (0001397814) era el de David F. Solomon,
    # de Forest Laboratories.
    {"cik": "0001693709", "name": "David Solomon", "role": "CEO", "org": "Goldman Sachs"},
    {"cik": "0001195071", "name": "Brian Moynihan", "role": "CEO", "org": "Bank of America"},
    {"cik": "0001316331", "name": "Pat Gelsinger", "role": "Ex-CEO", "org": "Intel"},
    {"cik": "0001492154", "name": "Mary Barra", "role": "CEO", "org": "General Motors"},
    {"cik": "0001335782", "name": "Doug McMillon", "role": "CEO", "org": "Walmart"},
    {"cik": "0001184237", "name": "Dara Khosrowshahi", "role": "CEO", "org": "Uber"},
]

# Operaciones importadas con un CIK que no era el de la persona. Se retiran en
# cada importación —no queda nada que retirar después de la primera—, para que
# el refresco programado limpie también producción.
MISATTRIBUTED: dict[str, set[str]] = {
    "Lisa Su": {"TZOO"},
    "David Solomon": {"FRX"},
}

# Valores de relleno que aparecen donde debería ir el símbolo cotizado.
NON_SYMBOLS = {"NONE", "N/A", "NA", "-", "--", "NULL"}

# Códigos de transacción del Form 4 (tabla II del formulario).
TRANSACTION_CODES = {
    "P": "Purchase",
    "S": "Sale",
    "A": "Grant",
    "M": "Option exercise",
    "F": "Tax withholding",
    "G": "Gift",
    "D": "Disposition",
    "C": "Conversion",
    "X": "Option exercise",
    "J": "Other",
    "W": "Inheritance",
    "I": "Discretionary",
    "L": "Small acquisition",
    "K": "Equity swap",
    "U": "Tender",
    "Z": "Voting trust",
    "E": "Derivative expiration",
    "H": "Derivative expiration",
    "O": "Option exercise",
}


def _parse_iso(value: Any) -> Optional[date]:
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _fetch(url: str, attempts: int = 3) -> bytes:
    """Descarga de EDGAR con reintentos.

    Un timeout de lectura no es un URLError sino un OSError suelto: sin
    capturarlo, una sola respuesta lenta tumbaba la importación entera a la
    segunda persona, y el refresco programado con ella.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            # 404 y compañía no mejoran esperando; 429 y 5xx sí.
            if error.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
        except OSError:
            if attempt == attempts - 1:
                raise
        time.sleep(2.0 * (attempt + 1))
    raise OSError(f"Sin respuesta de {url}")


def list_form4_filings(cik: str, limit: int = 12) -> list[dict[str, str]]:
    """Devuelve los Form 4 más recientes de una persona."""
    payload = json.loads(_fetch(f"https://data.sec.gov/submissions/CIK{cik}.json"))
    recent = payload.get("filings", {}).get("recent", {})
    filings = []
    for index, form in enumerate(recent.get("form", [])):
        if form != "4":
            continue
        filings.append(
            {
                "accession": recent["accessionNumber"][index].replace("-", ""),
                "document": recent["primaryDocument"][index],
                "filed": recent["filingDate"][index],
            }
        )
        if len(filings) >= limit:
            break
    return filings


_CLASS_IN_TITLE = re.compile(r"\bclass\s+([a-z])\b", re.IGNORECASE)
_CLASS_IN_SYMBOL = re.compile(r"^([A-Z]+)\.([A-Z])$")


def symbol_for_class(symbol: str, security_title: str) -> str:
    """Símbolo de la clase de acción que declara la línea, no la del emisor.

    El Form 4 de Berkshire trae "BRK.A" como símbolo del emisor, pero Buffett
    dona acciones de clase B. Guardadas como clase A, sus 12 millones de
    títulos B se habrían valorado a unos 700.000 dólares cada uno.
    """
    in_symbol = _CLASS_IN_SYMBOL.match(symbol or "")
    in_title = _CLASS_IN_TITLE.search(security_title or "")
    if not in_symbol or not in_title:
        return symbol
    declared = in_title.group(1).upper()
    if declared == in_symbol.group(2):
        return symbol
    return f"{in_symbol.group(1)}.{declared}"


def _ownership_line(node: ET.Element) -> str:
    """A nombre de quién están los títulos: directos o de qué sociedad o trust.

    Un mismo Form 4 declara por separado lo que la persona tiene a su nombre y
    lo que tiene a través de cada trust o sociedad. Cada línea lleva su propio
    saldo, y el total es la suma, no la última que aparezca.
    """
    kind = (node.findtext("ownershipNature/directOrIndirectOwnership/value") or "D").strip().upper()
    nature = node.findtext("ownershipNature/natureOfOwnership/value") or ""
    return f"{kind}:{' '.join(nature.lower().split())}"


def parse_form4(xml_bytes: bytes) -> dict[str, Any]:
    """Extrae emisor, transacciones no derivadas y saldos de un Form 4."""
    root = ET.fromstring(xml_bytes)

    symbol = (root.findtext("issuer/issuerTradingSymbol") or "").strip().upper()
    # Los Form 4 de empresas sin valor cotizado rellenan el campo con un texto
    # de relleno; guardarlo crearía un valor "NONE" imposible de cotizar.
    if symbol in NON_SYMBOLS:
        symbol = ""
    period = _parse_iso(root.findtext("periodOfReport"))

    transactions = []
    holdings = []
    for node in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = node.findtext("transactionCoding/transactionCode") or ""
        raw_date = node.findtext("transactionDate/value")
        shares = node.findtext("transactionAmounts/transactionShares/value") or "0"
        price = node.findtext("transactionAmounts/transactionPricePerShare/value") or "0"
        # Este es el dato que permite calcular patrimonio: cuántos títulos le
        # quedan al declarante después de la operación. El PTR del Congreso no
        # tiene equivalente, por eso los políticos no tienen posiciones.
        owned = node.findtext("postTransactionAmounts/sharesOwnedFollowingTransaction/value")
        # Con Decimal desde el texto del XML: el importe es títulos por precio
        # y en coma flotante arrastraba el error de los dos factores.
        shares_value = to_decimal(shares)
        price_value = to_decimal(price)
        try:
            traded_on = datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else None
        except (TypeError, ValueError):
            continue
        if not traded_on or shares_value is None or price_value is None:
            continue
        shares_owned = to_decimal(owned)
        transactions.append(
            {
                "trade_type": TRANSACTION_CODES.get(code, code or "Unknown"),
                "amount": money(shares_value * price_value),
                # La fecha de publicación la pone el filing, no la transacción:
                # la añade `fetch_insider_trades` con el filingDate de EDGAR.
                "transaction_date": traded_on,
                "shares": shares_value,
                "shares_owned": shares_owned,
                "symbol": symbol_for_class(symbol, node.findtext("securityTitle/value") or ""),
                "ownership": _ownership_line(node),
            }
        )

    # Las líneas sin operación: títulos que siguen en su poder a través de otra
    # vía (un trust, una fundación) y que el formulario declara igualmente.
    # Sin ellas, el saldo de quien vende desde una sociedad se quedaba en lo
    # que conserva esa sociedad.
    for node in root.findall("nonDerivativeTable/nonDerivativeHolding"):
        owned = node.findtext("postTransactionAmounts/sharesOwnedFollowingTransaction/value")
        shares_owned = to_decimal(owned)
        if shares_owned is None or period is None:
            continue
        holdings.append(
            {
                "symbol": symbol_for_class(symbol, node.findtext("securityTitle/value") or ""),
                "ownership": _ownership_line(node),
                "shares_owned": shares_owned,
                "as_of": period,
            }
        )

    return {
        "symbol": symbol,
        "issuer": (root.findtext("issuer/issuerName") or "").strip(),
        "transactions": transactions,
        "holdings": holdings,
        "derivatives": parse_derivatives(root, symbol, period),
    }


def parse_derivatives(root: ET.Element, symbol: str, period: Optional[date]) -> list[dict[str, Any]]:
    """Saldos de la tabla II: opciones, warrants, convertibles.

    Cada línea dice cuántos derechos quedan tras la operación
    (`sharesOwnedFollowingTransaction`) y en cuántas acciones del subyacente
    se traducen los de esa línea (`underlyingSecurityShares`). La proporción
    entre los dos da las acciones por derecho, que no siempre es uno.
    """
    lines = []
    nodes = [(node, True) for node in root.findall("derivativeTable/derivativeTransaction")]
    nodes += [(node, False) for node in root.findall("derivativeTable/derivativeHolding")]
    for node, is_transaction in nodes:
        title = " ".join((node.findtext("securityTitle/value") or "").split())
        owned = to_decimal(node.findtext("postTransactionAmounts/sharesOwnedFollowingTransaction/value"))
        underlying = to_decimal(node.findtext("underlyingSecurity/underlyingSecurityShares/value"))
        if not title or owned is None:
            continue

        # Acciones del subyacente por cada derecho. En una operación se mide
        # contra lo operado; en un saldo sin operación, contra lo que se tiene.
        reference = (
            to_decimal(node.findtext("transactionAmounts/transactionShares/value"))
            if is_transaction
            else owned
        )
        ratio = underlying / reference if underlying and reference else Decimal(1)

        as_of = _parse_iso(node.findtext("transactionDate/value")) if is_transaction else period
        if as_of is None:
            continue
        underlying_title = node.findtext("underlyingSecurity/underlyingSecurityTitle/value") or ""
        lines.append(
            {
                # El subyacente decide qué cotización vale: la clase B de Meta
                # se convierte en clase A, que es lo que cotiza como META.
                "symbol": symbol_for_class(symbol, underlying_title),
                "title": title,
                "exercise_price": to_decimal(node.findtext("conversionOrExercisePrice/value")),
                "expiration": _parse_iso(node.findtext("expirationDate/value")),
                "ownership": _ownership_line(node),
                "units_owned": owned,
                "ratio": ratio,
                "as_of": as_of,
            }
        )
    return lines


def _document_url(cik: str, accession: str, document: str) -> str:
    # El primaryDocument apunta a la versión renderizada (xslF345X0*/); el XML
    # crudo vive en la misma carpeta sin ese prefijo.
    filename = document.split("/")[-1]
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{filename}"


def fetch_insider_activity(insider: dict[str, str], filings_limit: int = 12) -> dict[str, Any]:
    """Descarga los Form 4 recientes de una persona: operaciones y saldos.

    Cada saldo lleva un orden (fecha, filing, línea) para poder quedarse con el
    último de cada vía de propiedad: dentro de un formulario con varias ventas
    el mismo día, el saldo bueno es el de la última línea, no el de la primera.
    """
    # `complete` dice si se leyeron todos los formularios: con alguno perdido
    # por la red, las posiciones no se reconstruyen para no borrar un saldo
    # que sólo faltaba por un fallo de conexión.
    activity: dict[str, Any] = {"trades": [], "positions": [], "derivatives": [], "complete": True}
    try:
        filings = list_form4_filings(insider["cik"], filings_limit)
    except (OSError, json.JSONDecodeError, KeyError):
        activity["complete"] = False
        return activity

    for filing_index, filing in enumerate(filings):
        time.sleep(REQUEST_PAUSE)
        url = _document_url(insider["cik"], filing["accession"], filing["document"])
        try:
            parsed = parse_form4(_fetch(url))
        except (OSError, ET.ParseError):
            activity["complete"] = False
            continue
        if not parsed["symbol"]:
            continue
        # `filingDate` es el día en que EDGAR publicó el Form 4: eso es lo que
        # la web llama fecha de publicación. La fecha que trae cada transacción
        # dentro del formulario es cuándo se operó, que es otra cosa.
        filed_on = _parse_iso(filing.get("filed"))
        if filed_on is None:
            continue
        # Los filings llegan del más reciente al más antiguo.
        recency = len(filings) - filing_index

        for line_index, transaction in enumerate(parsed["transactions"]):
            traded_on = transaction["transaction_date"]
            if traded_on > filed_on:
                # Imposible: nadie declara antes de operar. El formulario trae
                # la fecha mal escrita y no se puede adivinar la buena.
                traded_on = None
            activity["trades"].append(
                {
                    **transaction,
                    "reported_date": filed_on,
                    "transaction_date": traded_on,
                    "issuer_symbol": parsed["symbol"],
                    "issuer": parsed["issuer"],
                }
            )
            # `as_of` dice a qué día corresponde el saldo, así que sólo sirven
            # las líneas con fecha de ejecución fiable.
            if transaction["shares_owned"] is not None and traded_on is not None:
                activity["positions"].append(
                    {
                        "symbol": transaction["symbol"],
                        "issuer": parsed["issuer"],
                        "ownership": transaction["ownership"],
                        "shares_owned": transaction["shares_owned"],
                        "as_of": traded_on,
                        "order": (traded_on, recency, line_index),
                    }
                )

        offset = len(parsed["transactions"])
        for line_index, holding in enumerate(parsed["holdings"], start=offset):
            activity["positions"].append(
                {
                    **holding,
                    "issuer": parsed["issuer"],
                    "order": (holding["as_of"], recency, line_index),
                }
            )

        for line_index, derivative in enumerate(parsed["derivatives"]):
            if derivative["as_of"] > filed_on:
                continue
            activity["derivatives"].append(
                {
                    **derivative,
                    "issuer": parsed["issuer"],
                    "order": (derivative["as_of"], recency, line_index),
                }
            )
    return activity


def _ticker(db, symbol: str, issuer: str) -> Ticker:
    ticker = db.query(Ticker).filter(Ticker.symbol == symbol).one_or_none()
    if ticker is None:
        ticker = Ticker(symbol=symbol, name=issuer or symbol)
        db.add(ticker)
        db.flush()
    return ticker


def purge_misattributed(db, person: Politician) -> int:
    """Retira lo importado de otra persona con el mismo nombre."""
    symbols = MISATTRIBUTED.get(person.name)
    if not symbols:
        return 0
    ticker_ids = [
        ticker_id
        for (ticker_id,) in db.query(Ticker.id).filter(Ticker.symbol.in_(symbols)).all()
    ]
    if not ticker_ids:
        return 0
    removed = (
        db.query(Trade)
        .filter(Trade.politician_id == person.id, Trade.ticker_id.in_(ticker_ids))
        .delete(synchronize_session=False)
    )
    db.query(Holding).filter(
        Holding.politician_id == person.id, Holding.ticker_id.in_(ticker_ids)
    ).delete(synchronize_session=False)
    db.expire(person)
    return removed or 0


def import_insiders(
    limit_people: Optional[int] = None,
    filings_limit: int = 12,
    verbose: bool = True,
) -> dict[str, int]:
    """Vuelca en la base las operaciones declaradas por los insiders de la lista."""
    people = INSIDERS[:limit_people] if limit_people else INSIDERS
    imported_people = 0
    imported_trades = 0
    imported_holdings = 0
    prepare_database()

    with SessionLocal() as db:
        for insider in people:
            person = db.query(Politician).filter(Politician.name == insider["name"]).one_or_none()
            if person is not None:
                removed = purge_misattributed(db, person)
                if removed and verbose:
                    print(f"  {insider['name']}: {removed} operaciones de otra persona retiradas")
                db.commit()

            activity = fetch_insider_activity(insider, filings_limit)
            trades = activity["trades"]
            if not trades and not activity["positions"]:
                if verbose:
                    print(f"  {insider['name']}: sin Form 4 legibles")
                continue

            if person is None:
                person = Politician(
                    name=insider["name"],
                    chamber=insider["role"],
                    state=insider["org"],
                    party="Business",
                    category="business",
                )
                db.add(person)
                db.flush()
                imported_people += 1

            # Mismo redondeo en la clave que en la comparación: sin él falla
            # con importes de más de dos decimales y el insert choca contra el
            # índice de unicidad de trades.
            existing = {
                (
                    trade.ticker.symbol,
                    trade.trade_type,
                    trade.reported_date,
                    trade.transaction_date,
                    money(trade.amount),
                ): trade
                for trade in person.trades
            }

            for item in trades:
                ticker = _ticker(db, item["symbol"], item["issuer"])
                identity = (
                    item["trade_type"],
                    item["reported_date"],
                    item["transaction_date"],
                    money(item["amount"]),
                )
                key = (item["symbol"],) + identity
                if key in existing:
                    continue

                # Una operación guardada antes con el símbolo del emisor
                # ("BRK.A") siendo de otra clase ("BRK.B"): se corrige la que
                # hay en vez de añadir una segunda.
                mislabelled = existing.pop((item["issuer_symbol"],) + identity, None)
                if mislabelled is not None and item["issuer_symbol"] != item["symbol"]:
                    mislabelled.ticker_id = ticker.id
                    existing[key] = mislabelled
                    continue

                trade = Trade(
                    politician_id=person.id,
                    ticker_id=ticker.id,
                    trade_type=item["trade_type"],
                    amount=item["amount"],
                    reported_date=item["reported_date"],
                    transaction_date=item["transaction_date"],
                    notes=f"SEC Form 4 · {insider['org']}",
                )
                db.add(trade)
                existing[key] = trade
                imported_trades += 1

            if activity["complete"]:
                imported_holdings += _update_holdings(db, person, activity["positions"])
                _update_derivatives(db, person, activity["derivatives"])
            elif verbose:
                print(f"  {insider['name']}: faltan formularios, posiciones sin tocar")

            if verbose:
                print(f"  {insider['name']:22s} {len(trades):4d} operaciones leídas")
            db.commit()

    return {
        "people": imported_people,
        "trades": imported_trades,
        "holdings": imported_holdings,
    }


def aggregate_positions(positions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Saldo por valor: el último de cada vía de propiedad, sumados.

    Un directivo puede tener títulos a su nombre y a través de varios trusts o
    sociedades, y cada Form 4 declara el saldo de cada vía por separado.
    Quedarse con una sola línea dejaba, por ejemplo, a Zuckerberg con las
    acciones de una de sus sociedades en lugar de con todas.
    """
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for line in positions:
        key = (line["symbol"], line["ownership"])
        current = latest.get(key)
        if current is None or line["order"] > current["order"]:
            latest[key] = line

    totals: dict[str, dict[str, Any]] = {}
    for (symbol, _ownership), line in latest.items():
        entry = totals.setdefault(
            symbol,
            {
                "shares": ZERO,
                "shares_indirect": ZERO,
                "as_of": line["as_of"],
                "issuer": line.get("issuer", ""),
            },
        )
        shares = to_decimal(line["shares_owned"])
        entry["shares"] += shares
        if line["ownership"].startswith("I:"):
            entry["shares_indirect"] += shares
        entry["as_of"] = max(entry["as_of"], line["as_of"])
    return totals


def _update_holdings(db, person: Politician, positions: list[dict[str, Any]]) -> int:
    """Rehace las posiciones de la persona con lo que declaran sus Form 4 recientes.

    Se reconstruyen en lugar de parchearse: un saldo guardado con el símbolo
    equivocado o a partir de una sola línea de propiedad no se corregiría
    nunca si sólo se sobrescribiera con datos más nuevos.
    """
    totals = aggregate_positions(positions)
    if not totals:
        return 0

    current = {holding.ticker.symbol: holding for holding in person.holdings}
    for symbol, holding in current.items():
        if symbol not in totals:
            db.delete(holding)

    for symbol, entry in totals.items():
        ticker = _ticker(db, symbol, entry["issuer"])
        holding = current.get(symbol)
        if holding is None:
            holding = Holding(politician_id=person.id, ticker_id=ticker.id)
            db.add(holding)
        holding.shares = entry["shares"]
        holding.shares_indirect = entry["shares_indirect"]
        holding.as_of = entry["as_of"]
        holding.source = "SEC Form 4"

    return len(totals)


def aggregate_derivatives(
    lines: list[dict[str, Any]], today: Optional[date] = None
) -> list[dict[str, Any]]:
    """Derechos vivos: el último saldo de cada serie y vía de propiedad, sumados.

    Una serie es un mismo derecho —título, precio de ejercicio, vencimiento—:
    opciones con precios distintos no se pueden sumar porque no valen lo mismo.
    Las vencidas y las que quedaron a cero se descartan.
    """
    today = today or date.today()
    latest: dict[tuple, dict[str, Any]] = {}
    for line in lines:
        key = (line["symbol"], line["title"], line["exercise_price"], line["expiration"], line["ownership"])
        current = latest.get(key)
        if current is None or line["order"] > current["order"]:
            latest[key] = line

    series: dict[tuple, dict[str, Any]] = {}
    for (symbol, title, exercise_price, expiration, _ownership), line in latest.items():
        if expiration is not None and expiration < today:
            continue
        underlying = to_decimal(line["units_owned"]) * to_decimal(line["ratio"])
        if not underlying:
            continue
        entry = series.setdefault(
            (symbol, title, exercise_price, expiration),
            {
                "symbol": symbol,
                "title": title,
                "exercise_price": exercise_price,
                "expiration": expiration,
                "underlying_shares": ZERO,
                "as_of": line["as_of"],
                "issuer": line.get("issuer", ""),
            },
        )
        entry["underlying_shares"] += underlying
        entry["as_of"] = max(entry["as_of"], line["as_of"])
    return sorted(series.values(), key=lambda item: (item["symbol"], item["title"], item["expiration"] or date.max))


def _update_derivatives(db, person: Politician, lines: list[dict[str, Any]]) -> int:
    """Rehace los derechos de la persona; como las posiciones, no se parchean."""
    for derivative in list(person.derivatives):
        db.delete(derivative)
    db.flush()
    series = aggregate_derivatives(lines)
    for entry in series:
        ticker = _ticker(db, entry["symbol"], entry["issuer"])
        db.add(
            DerivativeHolding(
                politician_id=person.id,
                ticker_id=ticker.id,
                title=entry["title"][:255],
                underlying_shares=entry["underlying_shares"],
                exercise_price=entry["exercise_price"],
                expiration=entry["expiration"],
                as_of=entry["as_of"],
            )
        )
    return len(series)


if __name__ == "__main__":
    print("Importando Form 4 desde SEC EDGAR...")
    result = import_insiders()
    print(
        f"\nListo: {result['people']} personas nuevas, {result['trades']} operaciones nuevas, "
        f"{result['holdings']} posiciones recalculadas"
    )
