"""Ingesta de operaciones de directivos y grandes accionistas (SEC Form 4).

El equivalente empresarial del PTR del Congreso: la SEC obliga a directivos,
consejeros y accionistas de más del 10% a declarar sus operaciones en un
Formulario 4 dentro de los dos días hábiles siguientes.

Fuente: EDGAR (dominio público). La SEC exige un User-Agent identificable y
limita a 10 peticiones por segundo.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Any, Optional

from app.database import SessionLocal, prepare_database
from app.models import Holding, Politician, Ticker, Trade

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
    {"cik": "0001227903", "name": "Lisa Su", "role": "CEO", "org": "AMD"},
    {"cik": "0001834152", "name": "Brian Chesky", "role": "CEO", "org": "Airbnb"},
    {"cik": "0001294693", "name": "Marc Benioff", "role": "CEO", "org": "Salesforce"},
    {"cik": "0000901999", "name": "Larry Ellison", "role": "Presidente", "org": "Oracle"},
    {"cik": "0001397814", "name": "David Solomon", "role": "CEO", "org": "Goldman Sachs"},
    {"cik": "0001195071", "name": "Brian Moynihan", "role": "CEO", "org": "Bank of America"},
    {"cik": "0001316331", "name": "Pat Gelsinger", "role": "Ex-CEO", "org": "Intel"},
    {"cik": "0001492154", "name": "Mary Barra", "role": "CEO", "org": "General Motors"},
    {"cik": "0001335782", "name": "Doug McMillon", "role": "CEO", "org": "Walmart"},
    {"cik": "0001184237", "name": "Dara Khosrowshahi", "role": "CEO", "org": "Uber"},
]

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
}


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


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


def parse_form4(xml_bytes: bytes) -> dict[str, Any]:
    """Extrae emisor y transacciones no derivadas de un Form 4."""
    root = ET.fromstring(xml_bytes)
    transactions = []
    for node in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = node.findtext("transactionCoding/transactionCode") or ""
        raw_date = node.findtext("transactionDate/value")
        shares = node.findtext("transactionAmounts/transactionShares/value") or "0"
        price = node.findtext("transactionAmounts/transactionPricePerShare/value") or "0"
        # Este es el dato que permite calcular patrimonio: cuántos títulos le
        # quedan al declarante después de la operación. El PTR del Congreso no
        # tiene equivalente, por eso los políticos no tienen posiciones.
        owned = node.findtext("postTransactionAmounts/sharesOwnedFollowingTransaction/value")
        try:
            traded_on = datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else None
            amount = float(shares) * float(price)
        except (TypeError, ValueError):
            continue
        if not traded_on:
            continue
        try:
            shares_owned = float(owned) if owned is not None else None
        except ValueError:
            shares_owned = None
        transactions.append(
            {
                "trade_type": TRANSACTION_CODES.get(code, code or "Unknown"),
                "amount": round(amount, 2),
                "reported_date": traded_on,
                "shares": float(shares),
                "shares_owned": shares_owned,
            }
        )

    return {
        "symbol": (root.findtext("issuer/issuerTradingSymbol") or "").strip().upper(),
        "issuer": (root.findtext("issuer/issuerName") or "").strip(),
        "transactions": transactions,
    }


def _document_url(cik: str, accession: str, document: str) -> str:
    # El primaryDocument apunta a la versión renderizada (xslF345X0*/); el XML
    # crudo vive en la misma carpeta sin ese prefijo.
    filename = document.split("/")[-1]
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{filename}"


def fetch_insider_trades(insider: dict[str, str], filings_limit: int = 12) -> list[dict[str, Any]]:
    """Descarga y normaliza las operaciones declaradas por una persona."""
    collected: list[dict[str, Any]] = []
    try:
        filings = list_form4_filings(insider["cik"], filings_limit)
    except (urllib.error.URLError, json.JSONDecodeError, KeyError):
        return collected

    for filing in filings:
        time.sleep(REQUEST_PAUSE)
        url = _document_url(insider["cik"], filing["accession"], filing["document"])
        try:
            parsed = parse_form4(_fetch(url))
        except (urllib.error.URLError, ET.ParseError):
            continue
        if not parsed["symbol"]:
            continue
        for transaction in parsed["transactions"]:
            collected.append({**transaction, "symbol": parsed["symbol"], "issuer": parsed["issuer"]})
    return collected


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
            trades = fetch_insider_trades(insider, filings_limit)
            if not trades:
                if verbose:
                    print(f"  {insider['name']}: sin Form 4 legibles")
                continue

            person = db.query(Politician).filter(Politician.name == insider["name"]).one_or_none()
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

            existing = {
                (trade.ticker.symbol, trade.trade_type, trade.reported_date, round(trade.amount, 2))
                for trade in person.trades
            }

            for item in trades:
                ticker = db.query(Ticker).filter(Ticker.symbol == item["symbol"]).one_or_none()
                if ticker is None:
                    ticker = Ticker(symbol=item["symbol"], name=item["issuer"] or item["symbol"])
                    db.add(ticker)
                    db.flush()

                # Mismo redondeo que en `existing`: sin él la comparación falla
                # con importes de más de dos decimales y el insert choca contra
                # el índice de unicidad de trades.
                key = (
                    item["symbol"],
                    item["trade_type"],
                    item["reported_date"],
                    round(item["amount"], 2),
                )
                if key in existing:
                    continue
                existing.add(key)

                db.add(
                    Trade(
                        politician_id=person.id,
                        ticker_id=ticker.id,
                        trade_type=item["trade_type"],
                        amount=item["amount"],
                        reported_date=item["reported_date"],
                        notes=f"SEC Form 4 · {insider['org']}",
                    )
                )
                imported_trades += 1

            imported_holdings += _update_holdings(db, person, trades)

            if verbose:
                print(f"  {insider['name']:22s} {len(trades):4d} operaciones leídas")
            db.commit()

    return {
        "people": imported_people,
        "trades": imported_trades,
        "holdings": imported_holdings,
    }


def _update_holdings(db, person: Politician, trades: list[dict[str, Any]]) -> int:
    """Guarda la posición que declara el Form 4 más reciente de cada empresa.

    Los filings se recorren del más reciente al más antiguo, así que la primera
    aparición de cada símbolo es la posición vigente.
    """
    latest: dict[str, dict[str, Any]] = {}
    for item in trades:
        if item.get("shares_owned") is None:
            continue
        current = latest.get(item["symbol"])
        if current is None or item["reported_date"] > current["reported_date"]:
            latest[item["symbol"]] = item

    updated = 0
    for symbol, item in latest.items():
        ticker = db.query(Ticker).filter(Ticker.symbol == symbol).one_or_none()
        if ticker is None:
            continue

        holding = (
            db.query(Holding)
            .filter(Holding.politician_id == person.id, Holding.ticker_id == ticker.id)
            .one_or_none()
        )
        if holding is None:
            holding = Holding(politician_id=person.id, ticker_id=ticker.id)
            db.add(holding)
        elif holding.as_of >= item["reported_date"]:
            # Lo que ya hay es igual de reciente o más: no se pisa.
            continue

        holding.shares = item["shares_owned"]
        holding.as_of = item["reported_date"]
        holding.source = "SEC Form 4"
        updated += 1

    return updated


if __name__ == "__main__":
    print("Importando Form 4 desde SEC EDGAR...")
    result = import_insiders()
    print(f"\nListo: {result['people']} personas nuevas, {result['trades']} operaciones nuevas")
