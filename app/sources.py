from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from html import unescape
from typing import Any, Optional
from urllib.request import Request, urlopen

from app.ingestion import load_trade_records_into_db

LOGGER = logging.getLogger(__name__)

REAL_DATASET_URL = "https://raw.githubusercontent.com/TattooedHead/house-stock-watcher-data/master/data/all_transactions.json"


def _iso_from_us_date(value: Any) -> Optional[str]:
    """Convierte la fecha MM/DD/YYYY de la fuente a ISO, o None si no lo es.

    Sin valor por defecto a propósito: una fecha inventada en el hueco de una
    que falta es indistinguible de un dato declarado.
    """
    try:
        return datetime.strptime(str(value).strip(), "%m/%d/%Y").date().isoformat()
    except (TypeError, ValueError):
        return None


def parse_real_dataset(raw_json: str) -> list[dict[str, Any]]:
    """Parse a public House Stock Watcher JSON export into trade records."""
    try:
        payload = json.loads(raw_json or "[]")
    except json.JSONDecodeError:
        return []

    if not isinstance(payload, list):
        return []

    records: list[dict[str, Any]] = []
    for item in payload:
        ticker = (item.get("ticker") or "").strip()
        if not ticker:
            continue

        representative = (item.get("representative") or "Unknown Representative").strip()
        trade_type = str(item.get("type") or "Unknown")
        amount = item.get("amount_mid")
        if amount is None:
            amount_match = re.search(r"\$?([0-9,]+(?:\.\d+)?)", str(item.get("amount") or ""), flags=re.IGNORECASE)
            if amount_match:
                amount = float(amount_match.group(1).replace(",", ""))
            else:
                amount = 0.0

        # `disclosure_date` es cuándo se hizo público el filing y
        # `transaction_date` cuándo se ejecutó la operación: son cosas
        # distintas y la web las enseña por separado. Sin fecha de publicación
        # el registro no se puede situar en el tiempo, así que se descarta.
        reported_date = _iso_from_us_date(item.get("disclosure_date"))
        if reported_date is None:
            continue
        transaction_date = _iso_from_us_date(item.get("transaction_date"))

        # El district viene como "PA16": los dos primeros caracteres son el estado.
        district = str(item.get("district") or "").strip().upper()
        state = district[:2] if len(district) >= 2 and district[:2].isalpha() else ""

        records.append(
            {
                "politician_name": representative,
                "ticker": ticker.upper(),
                "trade_type": trade_type.title(),
                "amount": float(amount),
                "reported_date": reported_date,
                "transaction_date": transaction_date,
                "chamber": "House",
                "state": state or "Unknown",
            }
        )

    return records


def parse_official_html_filing(raw_html: str, politician_name: str) -> list[dict[str, Any]]:
    """Parse a disclosure page exported as HTML from a public official source.

    The goal is to support the actual pattern seen in Senate/House disclosures:
    repeated transaction blocks, each containing Ticker/Type/Amount/Date fields.
    """
    cleaned_html = unescape(raw_html or "")
    text = re.sub(r"<script.*?</script>", " ", cleaned_html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"\s+", " ", text)

    entries: list[dict[str, Any]] = []
    blocks = re.findall(
        r"(?:Transaction\s*\d*[:\-]?\s*.*?)(?=(?:Transaction\s*\d*[:\-]?|$))",
        cleaned_html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not blocks:
        blocks = [cleaned_html]

    for block in blocks:
        plain = re.sub(r"<[^>]+>", "\n", block)
        plain = unescape(plain)
        plain = re.sub(r"\s+", " ", plain).strip()
        if not plain:
            continue

        ticker_match = re.search(r"Ticker\s*[:\-]\s*([A-Za-z0-9.-]+)", plain, flags=re.IGNORECASE)
        type_match = re.search(r"Type\s*[:\-]\s*(Buy|Sell|Purchase|Sale)", plain, flags=re.IGNORECASE)
        amount_match = re.search(r"Amount\s*[:\-]\s*\$?\s*([0-9,]+(?:\.\d+)?)", plain, flags=re.IGNORECASE)
        date_match = re.search(r"Date\s*[:\-]\s*(\d{4}-\d{2}-\d{2})", plain, flags=re.IGNORECASE)

        # Sin ticker no hay operación, y sin fecha no hay forma de fecharla:
        # antes se rellenaba con el 1 de enero, que no lo había declarado nadie.
        if not ticker_match or not date_match:
            continue

        amount_text = amount_match.group(1).replace(",", "") if amount_match else "0"
        trade_type = type_match.group(1).title() if type_match else "Unknown"
        reported_date = date_match.group(1)

        entries.append(
            {
                "politician_name": politician_name,
                "ticker": ticker_match.group(1).upper(),
                "trade_type": trade_type,
                "amount": float(amount_text),
                "reported_date": reported_date,
            }
        )

    if not entries:
        fallback_match = re.search(r"Ticker\s*[:\-]\s*([A-Za-z0-9.-]+).*?Type\s*[:\-]\s*(Buy|Sell|Purchase|Sale).*?Amount\s*[:\-]\s*\$?\s*([0-9,]+(?:\.\d+)?) .*?Date\s*[:\-]\s*(\d{4}-\d{2}-\d{2})",
            text, flags=re.IGNORECASE | re.DOTALL)
        if fallback_match:
            return [{
                "politician_name": politician_name,
                "ticker": fallback_match.group(1).upper(),
                "trade_type": fallback_match.group(2).title(),
                "amount": float(fallback_match.group(3).replace(",", "")),
                "reported_date": fallback_match.group(4),
            }]

    return entries


def fetch_official_filing(url: str) -> str:
    """Download a filing page from a public URL."""
    request = Request(url, headers={"User-Agent": "TheWhaleFiles/1.0"})
    with urlopen(request, timeout=20) as response:
        payload = response.read()
    return payload.decode("utf-8", errors="ignore")


def ingest_official_filing(url: str, politician_name: str, database_url: str | None = None) -> list[dict[str, Any]]:
    """Fetch and import a single official filing."""
    raw_html = fetch_official_filing(url)
    parsed = parse_official_html_filing(raw_html, politician_name)
    return load_trade_records_into_db(parsed, database_url=database_url)


def fetch_real_dataset(url: str = REAL_DATASET_URL) -> str:
    """Download the public House Stock Watcher JSON export."""
    request = Request(url, headers={"User-Agent": "TheWhaleFiles/1.0"})
    with urlopen(request, timeout=30) as response:
        payload = response.read()
    return payload.decode("utf-8", errors="ignore")


def ingest_real_dataset(
    url: str = REAL_DATASET_URL,
    database_url: str | None = None,
    raw_json: str | None = None,
) -> list[dict[str, Any]]:
    """Import a public real dataset into the app database."""
    raw_json = raw_json if raw_json is not None else fetch_real_dataset(url)
    parsed = parse_real_dataset(raw_json)
    return load_trade_records_into_db(
        parsed,
        database_url=database_url,
        notes="Imported from House Stock Watcher dataset",
    )


def poll_official_sources(database_url: str | None = None) -> list[dict[str, Any]]:
    """Relee las fuentes públicas y guarda las operaciones que aún no estén.

    Sólo entra aquí lo que venga firmado por una persona identificada en el
    propio filing. Antes esta función también rascaba los buscadores del Senado
    y de la Cámara y atribuía lo que saliera a un nombre de ejemplo fijo: hoy
    no parseaban nada, pero el día que lo hubieran hecho habrían escrito en la
    base operaciones a nombre de alguien que no existe.
    """
    try:
        return ingest_real_dataset(database_url=database_url)
    except Exception:
        # La ingesta corre en un hilo de fondo y en un endpoint de
        # administración: un fallo de red no debe tumbar ninguno de los dos,
        # pero tampoco puede pasar en silencio.
        LOGGER.exception("Fallo al releer el dataset público")
        return []
