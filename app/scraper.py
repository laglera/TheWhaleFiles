import re
from typing import Any


def parse_senate_filing(raw_text: str, politician_name: str) -> list[dict[str, Any]]:
    """Parses a simplified Senate PTR-like filing into a list of trade dictionaries.

    This is a starter parser intentionally designed around the real structure of Senate
    disclosure files and a limited sample format. It is meant to be expanded later
    for official HTML/PDF content.
    """
    trades: list[dict[str, Any]] = []

    blocks = re.split(r"\n\s*Transaction\s*\d*:\s*\n", raw_text, flags=re.IGNORECASE)
    for block in blocks[1:]:
        ticker_match = re.search(r"Ticker:\s*([A-Za-z0-9.-]+)", block, flags=re.IGNORECASE)
        type_match = re.search(r"Type:\s*(Buy|Sell|Purchase|Sale)", block, flags=re.IGNORECASE)
        amount_match = re.search(r"Amount:\s*\$?\s*([0-9,]+(?:\.\d+)?)", block, flags=re.IGNORECASE)
        date_match = re.search(r"Date:\s*(\d{4}-\d{2}-\d{2})", block)

        if not ticker_match:
            continue

        trade_type = (type_match.group(1).strip() if type_match else "Unknown").title()
        amount_text = amount_match.group(1).replace(",", "") if amount_match else "0"
        amount = float(amount_text)
        reported_date = date_match.group(1) if date_match else "unknown"

        trades.append(
            {
                "politician_name": politician_name,
                "ticker": ticker_match.group(1).upper(),
                "trade_type": trade_type,
                "amount": amount,
                "reported_date": reported_date,
            }
        )

    return trades
