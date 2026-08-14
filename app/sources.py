from __future__ import annotations

import re
from html import unescape
from typing import Any
from urllib.request import Request, urlopen

from app.database import get_engine
from app.ingestion import load_filing_into_db
from app.models import Base

DEFAULT_SOURCE_URLS = [
    "https://efdsearch.senate.gov/search/",
    "https://disclosures-clerk.house.gov/",
]


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

        if not ticker_match:
            continue

        amount_text = amount_match.group(1).replace(",", "") if amount_match else "0"
        trade_type = type_match.group(1).title() if type_match else "Unknown"
        reported_date = date_match.group(1) if date_match else "2026-01-01"

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

    if not parsed:
        return []

    engine = get_engine(database_url or "sqlite:///./thewhalefiles.db")
    Base.metadata.create_all(bind=engine)

    imported: list[dict[str, Any]] = []
    for trade in parsed:
        imported.extend(
            load_filing_into_db(
                "\n".join([
                    f"Transaction:",
                    f"Ticker: {trade['ticker']}",
                    f"Type: {trade['trade_type']}",
                    f"Amount: ${trade['amount']:,.0f}",
                    f"Date: {trade['reported_date']}",
                ]),
                trade["politician_name"],
                database_url=database_url,
            )
        )
    return imported


def poll_official_sources(urls: list[str] | None = None, database_url: str | None = None) -> list[dict[str, Any]]:
    """Poll known official source URLs and import any new filings found."""
    source_urls = urls or DEFAULT_SOURCE_URLS
    results: list[dict[str, Any]] = []
    for url in source_urls:
        try:
            results.extend(ingest_official_filing(url, "Alex Morgan", database_url=database_url))
        except Exception:
            continue
    return results
