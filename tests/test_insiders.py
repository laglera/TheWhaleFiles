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


DERIVATIVE_FORM4 = b"""<?xml version="1.0"?>
<ownershipDocument>
  <periodOfReport>2026-07-14</periodOfReport>
  <issuer><issuerName>Meta Platforms, Inc.</issuerName><issuerTradingSymbol>META</issuerTradingSymbol></issuer>
  <derivativeTable>
    <derivativeTransaction>
      <securityTitle><value>Stock Option (Right to Buy)</value></securityTitle>
      <conversionOrExercisePrice><value>100.00</value></conversionOrExercisePrice>
      <transactionDate><value>2026-07-10</value></transactionDate>
      <transactionCoding><transactionCode>M</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>1000</value></transactionShares></transactionAmounts>
      <expirationDate><value>2030-01-01</value></expirationDate>
      <underlyingSecurity><underlyingSecurityTitle><value>Class A Common Stock</value></underlyingSecurityTitle>
        <underlyingSecurityShares><value>1000</value></underlyingSecurityShares></underlyingSecurity>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>4000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
    </derivativeTransaction>
    <derivativeHolding>
      <securityTitle><value>Class B Common Stock</value></securityTitle>
      <underlyingSecurity><underlyingSecurityTitle><value>Class A Common Stock</value></underlyingSecurityTitle>
        <underlyingSecurityShares><value>300</value></underlyingSecurityShares></underlyingSecurity>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>300</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>I</value></directOrIndirectOwnership>
        <natureOfOwnership><value>By CZI Holdings, LLC</value></natureOfOwnership></ownershipNature>
    </derivativeHolding>
    <derivativeHolding>
      <securityTitle><value>Stock Option (Right to Buy)</value></securityTitle>
      <conversionOrExercisePrice><value>20.00</value></conversionOrExercisePrice>
      <expirationDate><value>2020-01-01</value></expirationDate>
      <underlyingSecurity><underlyingSecurityShares><value>50</value></underlyingSecurityShares></underlyingSecurity>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>50</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
    </derivativeHolding>
  </derivativeTable>
</ownershipDocument>
"""


class DerivativeTests(unittest.TestCase):
    def lines(self):
        from app.insiders import parse_form4

        parsed = parse_form4(DERIVATIVE_FORM4)
        return [
            {**line, "order": (line["as_of"], 1, index)}
            for index, line in enumerate(parsed["derivatives"])
        ]

    def test_the_derivative_table_is_read(self):
        # Antes sólo se leía la tabla I: las opciones y la clase B de
        # Zuckerberg no existían para la web.
        lines = self.lines()
        self.assertEqual(len(lines), 3)
        option = lines[0]
        self.assertEqual(option["symbol"], "META")
        self.assertEqual(option["exercise_price"], 100)
        self.assertEqual(option["units_owned"], 4000)

    def test_expired_rights_are_dropped_and_series_kept_apart(self):
        from app.insiders import aggregate_derivatives

        series = aggregate_derivatives(self.lines(), today=date(2026, 8, 1))
        titles = {(item["title"], item["exercise_price"]) for item in series}
        self.assertEqual(
            titles, {("Stock Option (Right to Buy)", 100), ("Class B Common Stock", None)}
        )
        option = [item for item in series if item["exercise_price"] == 100][0]
        self.assertEqual(option["underlying_shares"], 4000)

    def test_intrinsic_value_ignores_out_of_the_money_rights(self):
        from types import SimpleNamespace

        from app.prices import combine_derivatives
        from tests.test_prices import quote

        def right(shares, strike):
            return SimpleNamespace(
                ticker=SimpleNamespace(symbol="META"),
                title="Option",
                underlying_shares=shares,
                exercise_price=strike,
                expiration=None,
                as_of=date(2026, 7, 1),
            )

        result = combine_derivatives(
            [right(4000, 100), right(300, None), right(10, 900)],
            {"META": quote("META", 500)},
        )
        # (500-100)*4000 + 500*300; la de 900 está fuera de dinero y vale 0.
        self.assertEqual(result["total"], 1_750_000)
        self.assertFalse([p for p in result["positions"] if p["exercise_price"] == 900][0]["in_the_money"])


class IndirectOwnershipTests(unittest.TestCase):
    def test_indirect_shares_are_kept_apart_within_the_total(self):
        totals = aggregate_positions(positions_from(parse_form4(FORM4)))
        self.assertEqual(totals["BRK.B"]["shares"], 1662)
        self.assertEqual(totals["BRK.B"]["shares_indirect"], 500)


OWNER_FORM4 = b"""<?xml version="1.0"?>
<ownershipDocument>
  <reportingOwner>
    <reportingOwnerId><rptOwnerCik>0001008463</rptOwnerCik><rptOwnerName>Tan Lip-Bu</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isDirector>1</isDirector><isOfficer>1</isOfficer>
      <officerTitle>Chief Executive Officer</officerTitle></reportingOwnerRelationship>
  </reportingOwner>
  <reportingOwner>
    <reportingOwnerId><rptOwnerCik>123</rptOwnerCik><rptOwnerName>DOE JOHN Q</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isOfficer>1</isOfficer><officerTitle>Former CEO</officerTitle></reportingOwnerRelationship>
  </reportingOwner>
</ownershipDocument>
"""


class DiscoveryTests(unittest.TestCase):
    def test_the_list_lives_in_a_data_file(self):
        # Antes eran 23 nombres en el código: añadir uno exigía redesplegar.
        from app.insiders import load_tracked

        tracked = load_tracked()
        self.assertGreaterEqual(len(tracked["people"]), 20)
        self.assertIn("NVDA", tracked["companies"])
        self.assertTrue(all(person["cik"].isdigit() for person in tracked["people"]))

    def test_reporting_owners_and_their_titles(self):
        from app.insiders import is_ceo, parse_reporting_owners

        owners = parse_reporting_owners(OWNER_FORM4)
        self.assertEqual(owners[0]["cik"], "0001008463")
        self.assertEqual(owners[0]["name"], "Lip-Bu Tan")
        self.assertTrue(is_ceo(owners[0]))
        # Quien fue CEO no cuenta como CEO.
        self.assertFalse(is_ceo(owners[1]))
        self.assertEqual(owners[1]["name"], "John Doe")

    def test_company_names_lose_their_legal_suffix(self):
        from app.insiders import organisation_name

        self.assertEqual(organisation_name("NVIDIA CORP"), "Nvidia")
        self.assertEqual(organisation_name("Apple Inc."), "Apple")
        self.assertEqual(organisation_name("JPMORGAN CHASE & CO"), "Jpmorgan Chase")

    def test_a_discovered_ceo_is_matched_by_cik_not_by_name(self):
        # EDGAR llama "Jen Hsun Huang" a quien la lista llama "Jensen Huang".
        from unittest import mock

        from app import insiders

        discovered = [
            {"cik": "0001197649", "name": "Jen Hsun Huang", "role": "CEO", "org": "Nvidia"},
            {"cik": "0001008463", "name": "Lip-Bu Tan", "role": "CEO", "org": "Intel"},
        ]
        with mock.patch.object(insiders, "discover_ceos", return_value=discovered):
            people = insiders.tracked_insiders()
        names = [person["name"] for person in people]
        self.assertIn("Jensen Huang", names)
        self.assertNotIn("Jen Hsun Huang", names)
        self.assertIn("Lip-Bu Tan", names)

    def test_discovery_reads_the_issuers_own_filings(self):
        from unittest import mock

        from app import insiders

        def fake_fetch(url, attempts=3):
            if url.endswith("company_tickers.json"):
                return b'{"0": {"cik_str": 50863, "ticker": "INTC", "title": "INTEL CORP"}}'
            return OWNER_FORM4

        filings = [{"accession": "1", "document": "a.xml", "filed": "2026-09-01"}]
        with mock.patch.object(insiders, "_fetch", side_effect=fake_fetch), mock.patch.object(
            insiders, "list_form4_filings", return_value=filings
        ) as listed, mock.patch.object(insiders, "REQUEST_PAUSE", 0):
            people = insiders.discover_ceos(["INTC"])
        listed.assert_called_once_with("0000050863", 20)
        self.assertEqual(people, [
            {"cik": "0001008463", "name": "Lip-Bu Tan", "role": "CEO", "org": "Intel", "discovered": True}
        ])

    def test_without_network_discovery_gives_nobody(self):
        from unittest import mock

        from app import insiders

        with mock.patch.object(insiders, "_fetch", side_effect=OSError("sin red")):
            self.assertEqual(insiders.discover_ceos(["INTC"]), [])


class DormantProfileTests(unittest.TestCase):
    def test_a_year_without_filings_is_said_on_the_profile(self):
        from datetime import timedelta

        from app import main
        from app.models import Politician, Ticker, Trade
        from tests.support import memory_session
        from tests.test_public_pages import make_request

        db = memory_session()
        person = Politician(name="Pat Gelsinger", chamber="Ex-CEO", state="Intel", category="business")
        ticker = Ticker(symbol="INTC", name="Intel")
        db.add_all([person, ticker])
        db.flush()
        db.add(Trade(politician_id=person.id, ticker_id=ticker.id, trade_type="Sale", amount=10,
                     reported_date=date.today() - timedelta(days=500)))
        db.flush()
        response = main.politician_detail_page(make_request(f"/politicians/{person.id}"), person.id, db)
        db.close()
        self.assertIsNotNone(response.context["dormant_since"])
        self.assertIn("Sin Formularios 4 desde", response.body.decode())
