"""Form 4 de la SEC: de qué clase son los títulos y cuántos quedan de verdad."""

import unittest
from datetime import date

from app.insiders import aggregate_positions, parse_form4, symbol_for_class

FORM4 = b"""<?xml version="1.0"?>
<ownershipDocument>
  <periodOfReport>2026-07-14</periodOfReport>
  <issuer><issuerName>BERKSHIRE HATHAWAY INC</issuerName><issuerTradingSymbol>BRK.A</issuerTradingSymbol></issuer>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Class B Common Stock</value></securityTitle>
      <transactionDate><value>2026-07-14</value></transactionDate>
      <transactionCoding><transactionCode>G</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>6000000</value></transactionShares>
        <transactionPricePerShare><value>0</value></transactionPricePerShare></transactionAmounts>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>6001162</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <securityTitle><value>Class B Common Stock</value></securityTitle>
      <transactionDate><value>2026-07-14</value></transactionDate>
      <transactionCoding><transactionCode>G</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>6000000</value></transactionShares>
        <transactionPricePerShare><value>0</value></transactionPricePerShare></transactionAmounts>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>1162</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
    </nonDerivativeTransaction>
    <nonDerivativeHolding>
      <securityTitle><value>Class B Common Stock</value></securityTitle>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>500</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>I</value></directOrIndirectOwnership>
        <natureOfOwnership><value>By  Trust</value></natureOfOwnership></ownershipNature>
    </nonDerivativeHolding>
  </nonDerivativeTable>
</ownershipDocument>
"""


def positions_from(parsed, recency=1):
    """Las mismas líneas que arma `fetch_insider_activity` para un filing."""
    lines = []
    for index, item in enumerate(parsed["transactions"]):
        lines.append(
            {
                "symbol": item["symbol"],
                "ownership": item["ownership"],
                "shares_owned": item["shares_owned"],
                "as_of": item["transaction_date"],
                "order": (item["transaction_date"], recency, index),
            }
        )
    offset = len(parsed["transactions"])
    for index, item in enumerate(parsed["holdings"], start=offset):
        lines.append({**item, "order": (item["as_of"], recency, index)})
    return lines


class ShareClassTests(unittest.TestCase):
    def test_class_b_shares_are_not_valued_as_class_a(self):
        self.assertEqual(symbol_for_class("BRK.A", "Class B Common Stock"), "BRK.B")
        self.assertEqual(symbol_for_class("BRK.A", "Class A Common Stock"), "BRK.A")
        self.assertEqual(symbol_for_class("TSLA", "Common Stock"), "TSLA")
        self.assertEqual(symbol_for_class("GOOGL", "Class C Capital Stock"), "GOOGL")

    def test_each_line_carries_its_own_class(self):
        parsed = parse_form4(FORM4)
        self.assertEqual({item["symbol"] for item in parsed["transactions"]}, {"BRK.B"})
        self.assertEqual(parsed["holdings"][0]["symbol"], "BRK.B")


class PositionTests(unittest.TestCase):
    def test_the_last_line_of_the_day_is_the_balance(self):
        # Dos donaciones el mismo día: la primera línea deja 6.001.162 títulos
        # y la segunda 1.162. Guardar la primera inflaba el saldo en 6 millones.
        totals = aggregate_positions(positions_from(parse_form4(FORM4)))
        # 1.162 directos más 500 a través de un trust.
        self.assertEqual(totals["BRK.B"]["shares"], 1662.0)
        self.assertEqual(totals["BRK.B"]["as_of"], date(2026, 7, 14))

    def test_every_ownership_line_adds_up(self):
        lines = [
            {"symbol": "META", "ownership": "I:by czi holdings, llc", "shares_owned": 100.0,
             "as_of": date(2026, 7, 1), "order": (date(2026, 7, 1), 2, 0)},
            {"symbol": "META", "ownership": "I:by foundation", "shares_owned": 50.0,
             "as_of": date(2026, 6, 1), "order": (date(2026, 6, 1), 1, 0)},
            # Un saldo más antiguo de la misma vía no suma: lo sustituye.
            {"symbol": "META", "ownership": "I:by czi holdings, llc", "shares_owned": 900.0,
             "as_of": date(2026, 5, 1), "order": (date(2026, 5, 1), 1, 1)},
        ]
        totals = aggregate_positions(lines)
        self.assertEqual(totals["META"]["shares"], 150.0)
        self.assertEqual(totals["META"]["as_of"], date(2026, 7, 1))


if __name__ == "__main__":
    unittest.main()
